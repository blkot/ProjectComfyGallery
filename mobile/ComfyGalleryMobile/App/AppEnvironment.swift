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
    private var didAttemptRestore = false

    enum Tab: String, Codable {
        case library, review, settings
    }

    init(
        apiClient: APIClient? = nil,
        connectionService: ConnectionService? = nil,
        mediaRepository: MediaRepository? = nil,
        reviewCommandQueue: ReviewCommandQueue? = nil,
        localStore: LocalStore? = nil
    ) {
        let store = localStore ?? LocalStore()
        let credentialStore = CredentialStore()
        let client = apiClient ?? APIClient(credentialStore: credentialStore)
        self.localStore = store
        self.apiClient = client
        self.connectionService = connectionService ?? ConnectionService(
            apiClient: client,
            credentialStore: credentialStore,
            localStore: store
        )
        self.mediaRepository = mediaRepository ?? MediaRepository(apiClient: client)
        self.reviewCommandQueue = reviewCommandQueue ?? ReviewCommandQueue(
            apiClient: client,
            localStore: store
        )
    }

    func handleScenePhase(_ phase: ScenePhase) {
        switch phase {
        case .active:
            Task { await restoreOrValidateConnection() }
        case .inactive, .background:
            Task { await flushPendingCommands() }
        @unknown default:
            break
        }
    }

    private func restoreOrValidateConnection() async {
        if !didAttemptRestore {
            didAttemptRestore = true
            await attemptRestore()
            return
        }
        guard isConnected else { return }
        do {
            let _: UserSession = try await apiClient.request(.authSession)
        } catch {
            isConnected = false
        }
    }

    private func attemptRestore() async {
        guard let profile = try? localStore.activeProfile(),
              let token = await connectionService.credentialStore.token(for: profile.uuid),
              !token.isEmpty,
              let baseURL = URL(string: profile.baseURL) else {
            return
        }
        await apiClient.configure(baseURL: baseURL)
        connectionService.baseURL = baseURL
        do {
            let health: Health = try await apiClient.request(.health)
            connectionService.serverVersion = health.version
            let session: UserSession = try await apiClient.request(.authSession)
            connectionService.connectionState = .connected(session)
            isConnected = true
        } catch {
            connectionService.connectionState = .error("Could not reconnect: \(error.localizedDescription)")
            isConnected = false
        }
    }

    private func flushPendingCommands() async {
        // Best-effort: nothing to flush synchronously since each command awaits inline.
    }
}
