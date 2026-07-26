import Foundation
import OSLog

@MainActor
@Observable
final class ConnectionService {
    let credentialStore: CredentialStore
    private let apiClient: APIClient
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "Connection")

    var connectionState: ConnectionState = .disconnected
    var serverVersion: String?
    var baseURL: URL?

    enum ConnectionState: Equatable {
        case disconnected
        case checkingServer
        case serverFound
        case authenticationRequired
        case authenticating
        case connected(UserSession)
        case error(String)

        static func == (lhs: ConnectionState, rhs: ConnectionState) -> Bool {
            switch (lhs, rhs) {
            case (.disconnected, .disconnected),
                 (.checkingServer, .checkingServer),
                 (.serverFound, .serverFound),
                 (.authenticationRequired, .authenticationRequired),
                 (.authenticating, .authenticating):
                return true
            case (.connected(let a), .connected(let b)):
                return a.user.id == b.user.id
            case (.error(let a), .error(let b)):
                return a == b
            default:
                return false
            }
        }
    }

    init(apiClient: APIClient, credentialStore: CredentialStore, localStore: LocalStore) {
        self.apiClient = apiClient
        self.credentialStore = credentialStore
        self.localStore = localStore
    }

    func connect(urlString: String, token: String? = nil) async {
        connectionState = .checkingServer

        guard let normalized = normalizeURL(urlString) else {
            connectionState = .error("Invalid URL. Enter a server address like http://192.168.50.68:8181")
            return
        }
        self.baseURL = normalized
        await apiClient.configure(baseURL: normalized)

        do {
            let health: Health = try await apiClient.request(.health)
            connectionState = .serverFound
            serverVersion = health.version
        } catch {
            connectionState = .error("Could not reach server. Check the address and ensure the server is running.")
            return
        }

        let tokenToUse: String
        if let token = token {
            tokenToUse = token
        } else if let saved = await credentialStore.token() {
            tokenToUse = saved
        } else {
            connectionState = .authenticationRequired
            return
        }

        await authenticate(token: tokenToUse, baseURL: normalized)
    }

    func authenticate(token: String, baseURL: URL? = nil) async {
        connectionState = .authenticating
        // Store token BEFORE API call so APIClient can attach it as Bearer header
        credentialStore.store(token: token, for: "default")
        do {
            let session: UserSession = try await apiClient.request(.authSession)
            // Update with real user ID from server
            credentialStore.store(token: token, for: session.user.id)
            if let baseURL = baseURL ?? self.baseURL {
                persistProfile(baseURL: baseURL, userID: session.user.id, token: token)
            }
            connectionState = .connected(session)
        } catch {
            credentialStore.delete(for: "default")
            connectionState = .error("Authentication failed. Check your API token.")
        }
    }

    func disconnect() async {
        if let profile = try? localStore.activeProfile() {
            await credentialStore.delete(for: profile.uuid)
        }
        await credentialStore.deleteAll()
        await apiClient.reset()
        try? await localStore.clearAll()
        baseURL = nil
        serverVersion = nil
        connectionState = .disconnected
    }

    private func persistProfile(baseURL: URL, userID: String, token: String) {
        let existing = try? localStore.activeProfile()
        let profile = existing ?? ServerProfile(
            baseURL: baseURL.absoluteString,
            displayName: nil,
            isActive: true
        )
        profile.baseURL = baseURL.absoluteString
        profile.lastServerVersion = serverVersion
        profile.lastConnectionDate = Date()
        profile.isActive = true
        if existing == nil {
            try? localStore.saveProfile(profile)
            // Re-store token keyed by the new profile UUID
            credentialStore.store(token: token, for: profile.uuid)
            // Clean up redundant intermediate keys
            credentialStore.delete(for: "default")
            credentialStore.delete(for: userID)
        } else {
            try? localStore.saveContext()
        }
    }

    private func normalizeURL(_ urlString: String) -> URL? {
        var string = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        if !string.hasPrefix("http://") && !string.hasPrefix("https://") {
            string = "http://\(string)"
        }
        guard let url = URL(string: string),
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.host != nil else {
            return nil
        }
        return components.url
    }
}
