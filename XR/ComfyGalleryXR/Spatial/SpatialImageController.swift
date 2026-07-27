import Foundation
import Observation
import RealityKit

@MainActor
@Observable
final class SpatialImageController {
    private struct CacheKey: Hashable {
        let profileID: UUID
        let mediaID: UUID
    }

    private struct CacheEntry {
        let image: ImagePresentationComponent.Spatial3DImage
        var accessOrder: UInt64
    }

    let entity = Entity()
    private(set) var state: SpatialGenerationState = .unavailable
    private(set) var mediaID: UUID?
    private(set) var hasGenerated = false
    private(set) var isPresentationReady = false
    private(set) var hasPresentationComponent = false

    @ObservationIgnored var onSpatialPresentationReady: ((UUID) -> Void)?

    @ObservationIgnored private var spatialImage: ImagePresentationComponent.Spatial3DImage?
    @ObservationIgnored private var generationTask: Task<Void, Never>?
    @ObservationIgnored private var presentationTask: Task<Void, Never>?
    @ObservationIgnored private var activeKey: CacheKey?
    @ObservationIgnored private var cache: [CacheKey: CacheEntry] = [:]
    @ObservationIgnored private var accessOrder: UInt64 = 0
    @ObservationIgnored private var isEntityMounted = false

    private let cacheLimit = 5

    /// Configures the selected image and restores its generated scene when the
    /// server/session preference says it should be spatial.
    @discardableResult
    func configure(
        profileID: UUID,
        mediaID: UUID,
        prefersSpatial: Bool
    ) -> Bool {
        deactivatePresentation()
        let key = CacheKey(profileID: profileID, mediaID: mediaID)
        activeKey = key
        self.mediaID = mediaID

        guard prefersSpatial, let entry = cache[key] else {
            state = .ready2D
            return false
        }

        touch(key)
        spatialImage = entry.image
        var component = ImagePresentationComponent(spatial3DImage: entry.image)
        component.desiredViewingMode = .spatial3D
        entity.components.set(component)
        hasPresentationComponent = true
        hasGenerated = true
        isPresentationReady = false
        state = .spatial
        verifySpatialPresentation(for: key, reportsGenerationSuccess: false)
        return true
    }

    func setUnavailable() {
        deactivatePresentation()
        mediaID = nil
        activeKey = nil
        state = .unavailable
    }

    func beginPreparing(profileID: UUID, mediaID: UUID) {
        deactivatePresentation()
        self.mediaID = mediaID
        activeKey = CacheKey(profileID: profileID, mediaID: mediaID)
        state = .generating
    }

    func generatePrepared(profileID: UUID, mediaID: UUID, fileURL: URL) {
        generationTask?.cancel()
        let key = CacheKey(profileID: profileID, mediaID: mediaID)
        activeKey = key
        self.mediaID = mediaID
        state = .generating
        generationTask = Task {
            do {
                let spatialImage = try await ImagePresentationComponent.Spatial3DImage(
                    contentsOf: fileURL
                )
                try Task.checkCancellation()
                guard activeKey == key else { return }

                self.spatialImage = spatialImage
                let component = ImagePresentationComponent(spatial3DImage: spatialImage)
                entity.components.set(component)
                hasPresentationComponent = true
                isPresentationReady = false

                // Match Apple's sample: first allow the component to stabilize in
                // mono, request spatial3D, and then let generate() own the scan.
                let monoIsReady = try await waitForStableMonoPresentation(key: key)
                try Task.checkCancellation()
                guard activeKey == key else { return }
                guard monoIsReady else {
                    failPresentation(
                        "RealityKit could not prepare the 2D image presentation.",
                        evictActiveEntry: true
                    )
                    return
                }

                guard var component = entity.components[ImagePresentationComponent.self] else {
                    failPresentation(
                        "RealityKit lost the image presentation before generating.",
                        evictActiveEntry: true
                    )
                    return
                }
                component.desiredViewingMode = .spatial3D
                entity.components.set(component)

                try await spatialImage.generate()
                try Task.checkCancellation()
                guard activeKey == key else { return }

                guard
                    let generatedComponent = entity.components[ImagePresentationComponent.self],
                    generatedComponent.availableViewingModes.contains(.spatial3D)
                else {
                    failPresentation(
                        "RealityKit did not produce a spatial scene for this image.",
                        evictActiveEntry: true
                    )
                    return
                }

                store(spatialImage, for: key)
                hasGenerated = true
                isPresentationReady = false
                state = .spatial
                verifySpatialPresentation(for: key, reportsGenerationSuccess: true)
            } catch is CancellationError {
                guard activeKey == key else { return }
                deactivatePresentation(keepingIdentity: true)
                state = .ready2D
            } catch {
                guard activeKey == key else { return }
                failPresentation(
                    "Spatial generation failed. The 2D image is still available.",
                    evictActiveEntry: true
                )
            }
        }
    }

    /// Temporarily switches the current generated component to mono while the
    /// backend disable operation is in flight. The cache remains available for a
    /// rollback if that write fails.
    func show2D() {
        guard
            hasGenerated,
            var component = entity.components[ImagePresentationComponent.self]
        else {
            return
        }
        presentationTask?.cancel()
        presentationTask = nil
        component.desiredViewingMode = .mono
        entity.components.set(component)
        isPresentationReady = false
        state = .ready2D
    }

    func showSpatial() {
        guard
            hasGenerated,
            var component = entity.components[ImagePresentationComponent.self]
        else {
            return
        }
        guard component.availableViewingModes.contains(.spatial3D) else {
            failPresentation(
                "The generated spatial scene is no longer available.",
                evictActiveEntry: true
            )
            return
        }
        component.desiredViewingMode = .spatial3D
        entity.components.set(component)
        isPresentationReady = false
        state = .spatial
        if let activeKey {
            verifySpatialPresentation(for: activeKey, reportsGenerationSuccess: false)
        }
    }

    func discard(profileID: UUID, mediaID: UUID) {
        let key = CacheKey(profileID: profileID, mediaID: mediaID)
        cache.removeValue(forKey: key)
        guard activeKey == key else { return }
        deactivatePresentation(keepingIdentity: true)
        state = .ready2D
    }

    func fail(_ message: String, mediaID: UUID) {
        guard self.mediaID == mediaID else { return }
        failPresentation(message, evictActiveEntry: true)
    }

    func cancelGeneration() {
        guard state == .generating else { return }
        generationTask?.cancel()
        generationTask = nil
        presentationTask?.cancel()
        presentationTask = nil
        deactivatePresentation(keepingIdentity: true)
        state = .ready2D
    }

    func deactivate() {
        deactivatePresentation()
        mediaID = nil
        activeKey = nil
        state = .ready2D
    }

    func clearAll() {
        cache.removeAll()
        deactivatePresentation()
        mediaID = nil
        activeKey = nil
        state = .unavailable
    }

    func handleMemoryPressure() {
        guard let activeKey else {
            cache.removeAll()
            return
        }
        cache = cache.filter { $0.key == activeKey }
    }

    func presentationDidMount() {
        isEntityMounted = true
    }

    func fit(
        presentationSize: SIMD2<Float>,
        availableSize: SIMD2<Float>
    ) {
        guard presentationSize != .zero else { return }
        entity.scale = ImagePresentationScaler.scale(
            presentationSize: presentationSize,
            availableSize: availableSize
        )
        let position = entity.position(relativeTo: nil)
        entity.setPosition(SIMD3(position.x, position.y, 0), relativeTo: nil)
    }

    private func waitForStableMonoPresentation(key expectedKey: CacheKey) async throws -> Bool {
        var stableChecks = 0
        for _ in 0..<120 {
            try Task.checkCancellation()
            guard activeKey == expectedKey else { return false }
            if
                isEntityMounted,
                let component = entity.components[ImagePresentationComponent.self],
                component.viewingMode == .mono,
                component.presentationScreenSize != .zero
            {
                stableChecks += 1
                if stableChecks >= 6 {
                    return true
                }
            } else {
                stableChecks = 0
            }
            try await Task.sleep(for: .milliseconds(50))
        }
        return false
    }

    private func verifySpatialPresentation(
        for expectedKey: CacheKey,
        reportsGenerationSuccess: Bool
    ) {
        presentationTask?.cancel()
        presentationTask = Task {
            for _ in 0..<80 {
                try? await Task.sleep(for: .milliseconds(50))
                guard !Task.isCancelled, activeKey == expectedKey else { return }
                guard let component = entity.components[ImagePresentationComponent.self] else {
                    continue
                }
                if component.viewingMode == .spatial3D {
                    isPresentationReady = true
                    if reportsGenerationSuccess {
                        onSpatialPresentationReady?(expectedKey.mediaID)
                    }
                    return
                }
            }
            guard !Task.isCancelled, activeKey == expectedKey else { return }
            isPresentationReady = false
            failPresentation(
                "RealityKit generated the scene but remained in 2D mode. Try another image or restart the viewer.",
                evictActiveEntry: true
            )
        }
    }

    private func failPresentation(_ message: String, evictActiveEntry: Bool) {
        if evictActiveEntry, let activeKey {
            cache.removeValue(forKey: activeKey)
        }
        if var component = entity.components[ImagePresentationComponent.self] {
            component.desiredViewingMode = .mono
            entity.components.set(component)
        }
        spatialImage = nil
        hasGenerated = false
        isPresentationReady = false
        state = .failed(message)
    }

    private func store(
        _ image: ImagePresentationComponent.Spatial3DImage,
        for key: CacheKey
    ) {
        accessOrder &+= 1
        cache[key] = CacheEntry(image: image, accessOrder: accessOrder)
        while cache.count > cacheLimit {
            guard
                let oldestKey = cache
                    .filter({ $0.key != activeKey })
                    .min(by: { $0.value.accessOrder < $1.value.accessOrder })?
                    .key
            else {
                break
            }
            cache.removeValue(forKey: oldestKey)
        }
    }

    private func touch(_ key: CacheKey) {
        guard var entry = cache[key] else { return }
        accessOrder &+= 1
        entry.accessOrder = accessOrder
        cache[key] = entry
    }

    private func deactivatePresentation(keepingIdentity: Bool = false) {
        generationTask?.cancel()
        generationTask = nil
        presentationTask?.cancel()
        presentationTask = nil
        spatialImage = nil
        hasGenerated = false
        isPresentationReady = false
        entity.components.remove(ImagePresentationComponent.self)
        hasPresentationComponent = false
        isEntityMounted = false
        if !keepingIdentity {
            mediaID = nil
            activeKey = nil
        }
    }
}
