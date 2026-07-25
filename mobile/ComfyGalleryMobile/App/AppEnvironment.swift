import SwiftUI
import SwiftData

@MainActor
@Observable
final class AppEnvironment {
    let apiClient: APIClient
    let connectionService: ConnectionService
    let mediaRepository: MediaRepository
    let reviewCommandQueue: ReviewCommandQueue
    let localStore: LocalStore

    var selectedTab: Tab = .library
    var isConnected = false
    var activeReviewSessionID: String?

    enum Tab: String, Codable {
        case library, review, settings
    }

    init(
        apiClient: APIClient = APIClient(credentialStore: CredentialStore()),
        connectionService: ConnectionService? = nil,
        mediaRepository: MediaRepository? = nil,
        reviewCommandQueue: ReviewCommandQueue? = nil,
        localStore: LocalStore = LocalStore()
    ) {
        let store = localStore
        self.localStore = store
        self.apiClient = apiClient
        self.connectionService = connectionService ?? ConnectionService(
            apiClient: apiClient,
            credentialStore: CredentialStore(),
            localStore: store
        )
        self.mediaRepository = mediaRepository ?? MediaRepository(apiClient: apiClient)
        self.reviewCommandQueue = reviewCommandQueue ?? ReviewCommandQueue(
            apiClient: apiClient,
            localStore: store
        )
    }

    func handleScenePhase(_ phase: ScenePhase) {
        switch phase {
        case .active:
            Task { await restoreAndReconcile() }
        case .inactive, .background:
            Task { await flushPendingCommands() }
        @unknown default:
            break
        }
    }

    private func restoreAndReconcile() async {
        guard isConnected else { return }
        do {
            let _: UserSession = try await apiClient.request(.authSession)
        } catch {
            isConnected = false
        }
    }

    private func flushPendingCommands() async {
        // Bounded best-effort command flush on backgrounding
    }
}
