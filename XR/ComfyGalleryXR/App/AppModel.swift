import Foundation
import Observation
import UIKit

enum ConnectionStep: Equatable {
    case checkingServer
    case authenticating

    var title: String {
        switch self {
        case .checkingServer: "Checking server…"
        case .authenticating: "Authenticating…"
        }
    }
}

enum ConnectionPhase: Equatable {
    case bootstrapping
    case disconnected
    case connecting(ConnectionStep)
    case connected(username: String)
    case offline
    case requiresAuthentication(String)

    var isUsable: Bool {
        switch self {
        case .connected, .offline: true
        default: false
        }
    }

    var needsConnectionWindow: Bool {
        switch self {
        case .disconnected, .requiresAuthentication: true
        default: false
        }
    }
}

enum LibraryLoadState: Equatable {
    case idle
    case initialLoading
    case refreshing
    case loaded
    case loadingNext
    case failedInitial(String)
    case failedRefresh(String)
    case failedNext(String)
    case exhausted
}

struct LibraryFeatureState {
    var scope = GalleryScope()
    var items: [XRMediaSummary] = []
    var total = 0
    var rawOffset = 0
    var loadState: LibraryLoadState = .idle
    var scrollAnchor: UUID?

    var canLoadNext: Bool {
        switch loadState {
        case .loaded, .failedNext: rawOffset < total
        default: false
        }
    }
}

enum ViewerLoadState: Equatable {
    case empty
    case loading
    case ready
    case unavailable(String)
    case failed(String)
}

struct ViewerFeatureState {
    var selection: ViewerSelection?
    var detail: XRMediaDetail?
    var navigation: MediaNavigation?
    var image: UIImage?
    var loadState: ViewerLoadState = .empty
    var videoIsPreparing = false

    var positionText: String {
        guard let navigation else { return "— / —" }
        return "\(navigation.position) / \(navigation.total)"
    }
}

@MainActor
@Observable
final class AppModel {
    private struct PendingPreferenceMutation {
        let profileID: UUID
        let kind: MediaKind
        let preferences: MediaPreferences
    }

    let environment: AppEnvironment
    let player = PlayerController()
    let spatial = SpatialImageController()

    var connectionPhase: ConnectionPhase = .bootstrapping
    var activeProfile: ServerProfile?
    var library = LibraryFeatureState()
    var viewer = ViewerFeatureState()
    var hasBootstrapped = false
    var hasPresentedConnection = false
    private(set) var preferenceSyncingIDs: Set<UUID> = []
    private(set) var preferenceSyncErrors: [UUID: String] = [:]

    @ObservationIgnored private var libraryGeneration = 0
    @ObservationIgnored private var viewerGeneration = 0
    @ObservationIgnored private var viewerLoadTask: Task<Void, Never>?
    @ObservationIgnored private var prefetchTasks: [Task<Void, Never>] = []
    @ObservationIgnored private var spatialPreparationTask: Task<Void, Never>?
    @ObservationIgnored private var pendingPreferenceMutations: [UUID: PendingPreferenceMutation] = [:]
    @ObservationIgnored private var preferenceSyncTasks: [UUID: Task<Void, Never>] = [:]

    init(environment: AppEnvironment) {
        self.environment = environment
        let restored = environment.persistence.loadLibraryState()
        library.scope = restored.0
        library.scrollAnchor = restored.1
        if let selectedID = restored.2 {
            viewer.selection = ViewerSelection(mediaID: selectedID, scope: restored.0)
        }
        spatial.onSpatialPresentationReady = { [weak self] mediaID in
            self?.spatialPresentationDidBecomeReady(mediaID: mediaID)
        }
    }

    func bootstrap() async {
        guard !hasBootstrapped else { return }
        defer { hasBootstrapped = true }

        guard let profile = environment.persistence.loadProfile() else {
            connectionPhase = .disconnected
            return
        }
        guard let token = try? environment.credentials.token(for: profile.id) else {
            activeProfile = profile
            connectionPhase = .requiresAuthentication("Paste a valid API token to reconnect.")
            return
        }

        activeProfile = profile
        await environment.api.configure(profile: profile, token: token)
        do {
            let user = try await environment.api.authenticate(baseURL: profile.baseURL, token: token)
            connectionPhase = .connected(username: user.username)
            await refreshLibrary()
            restoreViewerIfNeeded()
        } catch let error as APIClientError where error.requiresAuthentication {
            connectionPhase = .requiresAuthentication(error.errorDescription ?? "Authentication is required.")
        } catch {
            connectionPhase = .offline
            restoreViewerIfNeeded()
        }
    }

    func connect(baseURL rawBaseURL: String, token rawToken: String) async -> Bool {
        let token = rawToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            connectionPhase = .requiresAuthentication("Enter an API token.")
            return false
        }

        do {
            let baseURL = try BaseURLNormalizer.normalize(rawBaseURL)
            connectionPhase = .connecting(.checkingServer)
            _ = try await environment.api.checkHealth(baseURL: baseURL)
            connectionPhase = .connecting(.authenticating)
            let user = try await environment.api.authenticate(baseURL: baseURL, token: token)

            let profile: ServerProfile
            if let current = activeProfile,
               BaseURLNormalizer.isSameOrigin(current.baseURL, baseURL) {
                profile = ServerProfile(id: current.id, baseURL: baseURL, createdAt: current.createdAt)
            } else {
                profile = ServerProfile(baseURL: baseURL)
            }

            try environment.credentials.saveToken(token, for: profile.id)
            try environment.persistence.saveProfile(profile)
            activeProfile = profile
            await environment.api.configure(profile: profile, token: token)
            connectionPhase = .connected(username: user.username)
            hasPresentedConnection = true
            await refreshLibrary()
            restoreViewerIfNeeded()
            return true
        } catch let error as APIClientError where error.requiresAuthentication {
            connectionPhase = .requiresAuthentication(error.errorDescription ?? "The token was rejected.")
            return false
        } catch {
            connectionPhase = .requiresAuthentication(Redaction.safeErrorDescription(error))
            return false
        }
    }

    func disconnect() async {
        cancelAllWork()
        player.stop()
        preferenceSyncTasks.values.forEach { $0.cancel() }
        preferenceSyncTasks.removeAll()
        pendingPreferenceMutations.removeAll()
        preferenceSyncingIDs.removeAll()
        preferenceSyncErrors.removeAll()
        spatial.clearAll()
        if let profile = activeProfile {
            try? environment.credentials.deleteToken(for: profile.id)
        }
        try? environment.persistence.clearProfile()
        try? await environment.cache.clearAll()
        await environment.api.clearConfiguration()
        activeProfile = nil
        library = LibraryFeatureState(scope: library.scope)
        viewer = ViewerFeatureState()
        connectionPhase = .disconnected
        hasPresentedConnection = false
        environment.persistence.saveLibraryState(
            scope: library.scope,
            scrollAnchor: nil,
            selectedMediaID: nil
        )
    }

    func refreshLibrary() async {
        guard connectionPhase.isUsable else { return }
        libraryGeneration += 1
        let generation = libraryGeneration
        let hadItems = !library.items.isEmpty
        library.loadState = hadItems ? .refreshing : .initialLoading

        do {
            let page = try await environment.galleryRepository.page(
                scope: library.scope,
                offset: 0
            )
            guard generation == libraryGeneration else { return }
            apply(page: page, replacing: true)
        } catch {
            guard generation == libraryGeneration else { return }
            handle(error)
            let message = Redaction.safeErrorDescription(error)
            library.loadState = hadItems ? .failedRefresh(message) : .failedInitial(message)
        }
    }

    func loadNextPage() async {
        guard library.canLoadNext else { return }
        let generation = libraryGeneration
        library.loadState = .loadingNext
        do {
            let page = try await environment.galleryRepository.page(
                scope: library.scope,
                offset: library.rawOffset
            )
            guard generation == libraryGeneration else { return }
            apply(page: page, replacing: false)
        } catch {
            guard generation == libraryGeneration else { return }
            handle(error)
            library.loadState = .failedNext(Redaction.safeErrorDescription(error))
        }
    }

    func loadMoreIfNeeded(after item: XRMediaSummary) {
        guard
            let index = library.items.firstIndex(where: { $0.id == item.id }),
            index >= max(0, library.items.count - 12),
            library.canLoadNext
        else {
            return
        }
        Task { await loadNextPage() }
    }

    func updateScope(_ scope: GalleryScope) {
        guard scope != library.scope else { return }
        library.scope = scope
        environment.persistence.saveLibraryState(
            scope: scope,
            scrollAnchor: nil,
            selectedMediaID: viewer.selection?.mediaID
        )
        Task { await refreshLibrary() }
    }

    func updateScrollAnchor(_ mediaID: UUID?) {
        library.scrollAnchor = mediaID
        environment.persistence.saveLibraryState(
            scope: library.scope,
            scrollAnchor: mediaID,
            selectedMediaID: viewer.selection?.mediaID
        )
    }

    func preview(for media: XRMediaSummary, pixelSize: CGSize) async throws -> UIImage {
        guard let profile = activeProfile else { throw APIClientError.notConfigured }
        return try await environment.mediaRepository.preview(
            profileID: profile.id,
            media: media,
            targetPixelSize: pixelSize
        ).image
    }

    func select(_ summary: XRMediaSummary) {
        let selection = ViewerSelection(mediaID: summary.id, scope: library.scope)
        viewer.selection = selection
        var detail = XRMediaDetail(summary: summary)
        detail.preferences = effectivePreferences(
            mediaID: summary.id,
            serverPreferences: summary.preferences
        )
        viewer.detail = detail
        persistSelection(selection)
        startViewerLoad(selection)
    }

    func navigate(_ direction: NavigationDirection) {
        guard let navigation = viewer.navigation, let selection = viewer.selection else { return }
        let target: UUID?
        switch direction {
        case .previous: target = navigation.previousID
        case .next: target = navigation.nextID
        }
        guard let target else { return }
        let newSelection = ViewerSelection(mediaID: target, scope: selection.scope)
        viewer.selection = newSelection
        viewer.detail = nil
        persistSelection(newSelection)
        startViewerLoad(newSelection)
    }

    func retryViewer() {
        guard let selection = viewer.selection else { return }
        startViewerLoad(selection)
    }

    func closeViewer() {
        viewerLoadTask?.cancel()
        viewerLoadTask = nil
        prefetchTasks.forEach { $0.cancel() }
        prefetchTasks.removeAll()
        player.stop()
        cancelSpatial()
        spatial.deactivate()
    }

    func makeSpatial() {
        guard
            let profile = activeProfile,
            let detail = viewer.detail,
            SpatialEligibility.evaluate(
                kind: detail.kind,
                width: detail.width,
                height: detail.height
            ) == .eligible
        else {
            return
        }
        spatialPreparationTask?.cancel()
        spatial.beginPreparing(profileID: profile.id, mediaID: detail.id)
        spatialPreparationTask = Task {
            do {
                let url = try await environment.mediaRepository.spatialImageFile(
                    profileID: profile.id,
                    media: detail
                )
                try Task.checkCancellation()
                guard viewer.selection?.mediaID == detail.id else { return }
                spatial.generatePrepared(
                    profileID: profile.id,
                    mediaID: detail.id,
                    fileURL: url
                )
            } catch is CancellationError {
                spatial.cancelGeneration()
            } catch {
                spatial.fail(Redaction.safeErrorDescription(error), mediaID: detail.id)
            }
        }
    }

    func cancelSpatial() {
        spatialPreparationTask?.cancel()
        spatialPreparationTask = nil
        spatial.cancelGeneration()
    }

    func toggleFavoriteForCurrentMedia() {
        guard let detail = viewer.detail else { return }
        setFavorite(
            !detail.favorite,
            mediaID: detail.id,
            kind: detail.kind
        )
    }

    func setFavorite(_ isFavorite: Bool, for media: XRMediaSummary) {
        setFavorite(isFavorite, mediaID: media.id, kind: media.kind)
    }

    func disableSpatial() {
        guard
            let detail = viewer.detail,
            detail.kind == .image,
            detail.spatialViewPreferred || spatial.hasGenerated
        else {
            return
        }
        spatial.show2D()
        queuePreferenceMutation(
            mediaID: detail.id,
            kind: detail.kind,
            preferences: MediaPreferences(
                favorite: false,
                spatialViewPreferred: false
            )
        )
    }

    func enableCachedSpatial() {
        guard
            let detail = viewer.detail,
            detail.kind == .image,
            spatial.hasGenerated
        else {
            return
        }
        spatial.showSpatial()
        queuePreferenceMutation(
            mediaID: detail.id,
            kind: detail.kind,
            preferences: MediaPreferences(
                favorite: true,
                spatialViewPreferred: true
            )
        )
    }

    func retryPreferenceSyncForCurrentMedia() {
        guard let mediaID = viewer.detail?.id else { return }
        retryPreferenceSync(mediaID: mediaID)
    }

    func retryPreferenceSync(mediaID: UUID) {
        preferenceSyncErrors.removeValue(forKey: mediaID)
        startPreferenceSync(mediaID: mediaID)
    }

    func isPreferenceSyncing(mediaID: UUID) -> Bool {
        preferenceSyncingIDs.contains(mediaID)
    }

    func preferenceSyncError(mediaID: UUID) -> String? {
        preferenceSyncErrors[mediaID]
    }

    func viewerScenePhaseChanged(isActive: Bool) {
        if isActive {
            player.resumeIfAppropriate()
        } else {
            player.pause()
            cancelSpatial()
        }
    }

    func libraryScenePhaseChanged(isActive: Bool) {
        if !isActive {
            prefetchTasks.forEach { $0.cancel() }
            prefetchTasks.removeAll()
        }
    }

    func handleMemoryPressure() {
        prefetchTasks.forEach { $0.cancel() }
        prefetchTasks.removeAll()
        Task { await environment.mediaRepository.clearMemory() }
        spatial.handleMemoryPressure()
    }

    private func restoreViewerIfNeeded() {
        if let selection = viewer.selection {
            startViewerLoad(selection)
        }
    }

    private func startViewerLoad(_ selection: ViewerSelection) {
        viewerLoadTask?.cancel()
        prefetchTasks.forEach { $0.cancel() }
        prefetchTasks.removeAll()
        spatialPreparationTask?.cancel()
        spatial.deactivate()
        player.stop()
        viewerGeneration += 1
        let generation = viewerGeneration
        viewer.loadState = .loading
        viewer.image = nil
        viewer.navigation = nil
        viewer.videoIsPreparing = false
        viewerLoadTask = Task {
            await loadViewer(selection, generation: generation)
        }
    }

    private func loadViewer(_ selection: ViewerSelection, generation: Int) async {
        guard let profile = activeProfile else {
            viewer.loadState = .failed("Connect to a gallery first.")
            return
        }
        do {
            async let detailRequest = environment.galleryRepository.detail(id: selection.mediaID)
            async let navigationRequest = environment.galleryRepository.navigation(
                id: selection.mediaID,
                scope: selection.scope
            )
            var detail = try await detailRequest
            let navigation = try? await navigationRequest
            guard generation == viewerGeneration else { return }
            let serverPreferences = detail.preferences
            let normalizedServerPreferences =
                serverPreferences.enforcingSpatialFavoriteInvariant
            detail.preferences = effectivePreferences(
                mediaID: detail.id,
                serverPreferences: normalizedServerPreferences
            )
            viewer.detail = detail
            viewer.navigation = navigation
            let shouldGeneratePreferredSpatial = configureSpatialAvailability(
                for: detail,
                profile: profile
            )

            let preview = try await environment.mediaRepository.viewerImage(
                profileID: profile.id,
                media: detail,
                targetPixelSize: CGSize(width: 2_000, height: 2_000)
            )
            guard generation == viewerGeneration else { return }
            viewer.image = preview.image

            if detail.kind == .video {
                viewer.videoIsPreparing = true
                let fileURL = try await environment.mediaRepository.videoFile(
                    profileID: profile.id,
                    media: detail
                )
                guard generation == viewerGeneration else { return }
                player.load(fileURL: fileURL, autoplay: true)
                viewer.videoIsPreparing = false
            }
            viewer.loadState = .ready
            schedulePrefetch(navigation: navigation, scope: selection.scope, profile: profile)

            if normalizedServerPreferences != serverPreferences {
                queuePreferenceMutation(
                    mediaID: detail.id,
                    kind: detail.kind,
                    preferences: normalizedServerPreferences
                )
            } else if pendingPreferenceMutations[detail.id] != nil {
                startPreferenceSync(mediaID: detail.id)
            }

            if shouldGeneratePreferredSpatial {
                makeSpatial()
            }
        } catch let error as APIClientError {
            guard generation == viewerGeneration else { return }
            handle(error)
            if case .server(let status, _, _, _) = error, status == 404 {
                viewer.loadState = .unavailable("This media is no longer available.")
            } else {
                viewer.loadState = .failed(error.errorDescription ?? "The media could not be loaded.")
            }
        } catch is CancellationError {
            return
        } catch {
            guard generation == viewerGeneration else { return }
            viewer.loadState = .failed(Redaction.safeErrorDescription(error))
        }
    }

    private func schedulePrefetch(
        navigation: MediaNavigation?,
        scope: GalleryScope,
        profile: ServerProfile
    ) {
        guard let navigation else { return }
        if let next = navigation.nextID {
            prefetchTasks.append(
                Task(priority: .userInitiated) {
                    await self.prefetch(mediaID: next, profile: profile)
                }
            )
        }
        if let previous = navigation.previousID {
            prefetchTasks.append(
                Task(priority: .utility) {
                    await self.prefetch(mediaID: previous, profile: profile)
                }
            )
        }
    }

    private func prefetch(mediaID: UUID, profile: ServerProfile) async {
        guard let detail = try? await environment.galleryRepository.detail(id: mediaID) else { return }
        if detail.kind == .video {
            _ = try? await environment.mediaRepository.viewerImage(
                profileID: profile.id,
                media: detail,
                targetPixelSize: CGSize(width: 1_200, height: 1_200)
            )
            if detail.byteSize <= 40 * 1_024 * 1_024 {
                _ = try? await environment.mediaRepository.videoFile(
                    profileID: profile.id,
                    media: detail
                )
            }
        } else if detail.kind == .image {
            _ = try? await environment.mediaRepository.viewerImage(
                profileID: profile.id,
                media: detail,
                targetPixelSize: CGSize(width: 1_600, height: 1_600)
            )
        }
    }

    private func apply(page: MediaPage, replacing: Bool) {
        let effectiveItems = page.items.map { item in
            var item = item
            item.preferences = effectivePreferences(
                mediaID: item.id,
                serverPreferences: item.preferences.enforcingSpatialFavoriteInvariant
            )
            return item
        }
        let effectivePage = MediaPage(
            items: effectiveItems,
            total: page.total,
            limit: page.limit,
            offset: page.offset
        )
        let result = MediaPageAccumulator.accumulate(
            existing: library.items,
            page: effectivePage,
            replacing: replacing
        )
        library.items = result.items
        library.total = effectivePage.total
        library.rawOffset = result.rawOffset
        library.loadState = result.isExhausted ? .exhausted : .loaded
    }

    private func configureSpatialAvailability(
        for detail: XRMediaDetail,
        profile: ServerProfile
    ) -> Bool {
        #if targetEnvironment(simulator)
        spatial.setUnavailable()
        return false
        #else
        switch SpatialEligibility.evaluate(kind: detail.kind, width: detail.width, height: detail.height) {
        case .eligible:
            let restored = spatial.configure(
                profileID: profile.id,
                mediaID: detail.id,
                prefersSpatial: detail.spatialViewPreferred
            )
            return detail.spatialViewPreferred && !restored
        case .unavailable:
            spatial.setUnavailable()
            return false
        }
        #endif
    }

    private func setFavorite(
        _ isFavorite: Bool,
        mediaID: UUID,
        kind: MediaKind
    ) {
        guard let current = currentPreferences(mediaID: mediaID) else { return }

        // Spatial is the stronger state. Its favorite may only be removed through
        // Disable Spatial so the two flags cannot diverge.
        guard isFavorite || !current.spatialViewPreferred else { return }
        let desired = MediaPreferences(
            favorite: isFavorite,
            spatialViewPreferred: current.spatialViewPreferred
        ).enforcingSpatialFavoriteInvariant
        guard desired != current || pendingPreferenceMutations[mediaID] != nil else {
            return
        }
        queuePreferenceMutation(
            mediaID: mediaID,
            kind: kind,
            preferences: desired
        )
    }

    private func spatialPresentationDidBecomeReady(mediaID: UUID) {
        guard
            let detail = viewer.detail,
            detail.id == mediaID
        else {
            return
        }
        let desired = MediaPreferences(
            favorite: true,
            spatialViewPreferred: true
        )
        if detail.preferences == desired,
           pendingPreferenceMutations[mediaID] == nil {
            return
        }
        queuePreferenceMutation(
            mediaID: mediaID,
            kind: detail.kind,
            preferences: desired
        )
    }

    private func queuePreferenceMutation(
        mediaID: UUID,
        kind: MediaKind,
        preferences: MediaPreferences
    ) {
        guard let profile = activeProfile else { return }
        let normalized = preferences.enforcingSpatialFavoriteInvariant
        pendingPreferenceMutations[mediaID] = PendingPreferenceMutation(
            profileID: profile.id,
            kind: kind,
            preferences: normalized
        )
        preferenceSyncErrors.removeValue(forKey: mediaID)
        applyPreferencesLocally(mediaID: mediaID, preferences: normalized)
        startPreferenceSync(mediaID: mediaID)
    }

    private func startPreferenceSync(mediaID: UUID) {
        guard
            preferenceSyncTasks[mediaID] == nil,
            let mutation = pendingPreferenceMutations[mediaID]
        else {
            return
        }
        preferenceSyncingIDs.insert(mediaID)
        preferenceSyncTasks[mediaID] = Task {
            do {
                try await persistPreferenceMutation(mediaID: mediaID, mutation: mutation)
                finishPreferenceSync(
                    mediaID: mediaID,
                    attempted: mutation,
                    error: nil
                )
            } catch is CancellationError {
                preferenceSyncTasks[mediaID] = nil
                preferenceSyncingIDs.remove(mediaID)
            } catch {
                handle(error)
                finishPreferenceSync(
                    mediaID: mediaID,
                    attempted: mutation,
                    error: Redaction.safeErrorDescription(error)
                )
            }
        }
    }

    private func persistPreferenceMutation(
        mediaID: UUID,
        mutation: PendingPreferenceMutation
    ) async throws {
        for write in MediaPreferenceMutationPlan.writes(
            kind: mutation.kind,
            desired: mutation.preferences
        ) {
            switch write {
            case .favorite(let value):
                let favorite = try await environment.galleryRepository.updateFavorite(
                    id: mediaID,
                    isFavorite: value
                )
                guard favorite.favorite == value else {
                    throw APIClientError.invalidResponse
                }
            case .spatial(let value):
                let spatial = try await environment.galleryRepository.updateSpatialPreference(
                    id: mediaID,
                    isPreferred: value
                )
                guard spatial.spatialViewPreferred == value else {
                    throw APIClientError.invalidResponse
                }
            }
        }
    }

    private func finishPreferenceSync(
        mediaID: UUID,
        attempted: PendingPreferenceMutation,
        error: String?
    ) {
        preferenceSyncTasks[mediaID] = nil
        preferenceSyncingIDs.remove(mediaID)

        guard
            let current = pendingPreferenceMutations[mediaID],
            current.profileID == attempted.profileID,
            current.preferences == attempted.preferences
        else {
            startPreferenceSync(mediaID: mediaID)
            return
        }

        if let error {
            preferenceSyncErrors[mediaID] =
                "The preference is kept for this app session but could not be synced: \(error)"
            return
        }

        pendingPreferenceMutations.removeValue(forKey: mediaID)
        preferenceSyncErrors.removeValue(forKey: mediaID)
        applyPreferencesLocally(
            mediaID: mediaID,
            preferences: attempted.preferences
        )
        reconcileLibraryMembership(mediaID: mediaID)

        if !attempted.preferences.spatialViewPreferred {
            spatial.discard(
                profileID: attempted.profileID,
                mediaID: mediaID
            )
        }
    }

    private func effectivePreferences(
        mediaID: UUID,
        serverPreferences: MediaPreferences
    ) -> MediaPreferences {
        (
            pendingPreferenceMutations[mediaID]?.preferences
                ?? serverPreferences
        ).enforcingSpatialFavoriteInvariant
    }

    private func currentPreferences(mediaID: UUID) -> MediaPreferences? {
        if let detail = viewer.detail, detail.id == mediaID {
            return detail.preferences
        }
        return library.items.first(where: { $0.id == mediaID })?.preferences
    }

    private func applyPreferencesLocally(
        mediaID: UUID,
        preferences: MediaPreferences
    ) {
        if let index = library.items.firstIndex(where: { $0.id == mediaID }) {
            library.items[index].preferences = preferences
        }
        if var detail = viewer.detail, detail.id == mediaID {
            detail.preferences = preferences
            viewer.detail = detail
        }
    }

    private func reconcileLibraryMembership(mediaID: UUID) {
        let matches: (MediaPreferences) -> Bool = { preferences in
            switch self.library.scope.preference {
            case .all: true
            case .favorites: preferences.favorite
            case .spatial: preferences.spatialViewPreferred
            }
        }

        if let index = library.items.firstIndex(where: { $0.id == mediaID }) {
            guard !matches(library.items[index].preferences) else { return }
            library.items.remove(at: index)
            library.total = max(0, library.total - 1)
            library.rawOffset = max(0, library.rawOffset - 1)
            return
        }

        guard
            library.scope.preference != .all,
            let preferences = currentPreferences(mediaID: mediaID),
            matches(preferences)
        else {
            return
        }
        Task { await refreshLibrary() }
    }

    private func persistSelection(_ selection: ViewerSelection) {
        environment.persistence.saveLibraryState(
            scope: library.scope,
            scrollAnchor: library.scrollAnchor,
            selectedMediaID: selection.mediaID
        )
    }

    private func handle(_ error: Error) {
        guard let apiError = error as? APIClientError, apiError.requiresAuthentication else { return }
        player.pause()
        connectionPhase = .requiresAuthentication(apiError.errorDescription ?? "Authentication is required.")
        hasPresentedConnection = false
    }

    private func cancelAllWork() {
        libraryGeneration += 1
        viewerGeneration += 1
        viewerLoadTask?.cancel()
        viewerLoadTask = nil
        spatialPreparationTask?.cancel()
        spatialPreparationTask = nil
        prefetchTasks.forEach { $0.cancel() }
        prefetchTasks.removeAll()
    }
}
