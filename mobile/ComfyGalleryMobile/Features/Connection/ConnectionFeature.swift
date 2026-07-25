import SwiftUI
import OSLog

@MainActor
@Observable
final class ConnectionFeature {
    var serverURL: String = UserDefaults.standard.string(forKey: "lastServerURL") ?? ""
    var apiToken: String = ""
    var isConnecting = false
    var errorMessage: String?
    var showHTTPWarning = false
    var pendingURL: String?

    private let connectionService: ConnectionService
    private let environment: AppEnvironment

    init(connectionService: ConnectionService, environment: AppEnvironment) {
        self.connectionService = connectionService
        self.environment = environment
    }

    func connect() async {
        guard !serverURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Enter a server address."
            return
        }
        isConnecting = true
        errorMessage = nil

        let trimmed = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.lowercased().hasPrefix("http://") {
            showHTTPWarning = true
            pendingURL = trimmed
            isConnecting = false
            return
        }

        await performConnect(url: trimmed)
    }

    func confirmHTTP() async {
        showHTTPWarning = false
        guard let url = pendingURL else { return }
        isConnecting = true
        await performConnect(url: url)
    }

    func cancelHTTP() {
        showHTTPWarning = false
        pendingURL = nil
    }

    private func performConnect(url: String) async {
        let token = apiToken.trimmingCharacters(in: .whitespacesAndNewlines)
        let tokenParam = token.isEmpty ? nil : token
        await connectionService.connect(urlString: url, token: tokenParam)

        switch connectionService.connectionState {
        case .connected:
            UserDefaults.standard.set(url, forKey: "lastServerURL")
            environment.isConnected = true
        case .error(let message):
            errorMessage = message
        default:
            break
        }
        isConnecting = false
    }

    func pasteTokenAndConnect() async {
        guard let token = UIPasteboard.general.string?.trimmingCharacters(in: .whitespacesAndNewlines),
              !token.isEmpty else {
            errorMessage = "No token found in clipboard."
            return
        }
        apiToken = token
        await connect()
    }
}
