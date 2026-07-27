import SwiftUI
import UIKit

struct ConnectionView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismissWindow) private var dismissWindow

    @State private var baseURL = ""
    @State private var token = ""
    @State private var showHTTPWarning = false
    @State private var didPopulateURL = false

    private var isWorking: Bool {
        if case .connecting = model.connectionPhase { true } else { false }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Connect to Gallery")
                    .font(.largeTitle.bold())
                Text("Your address and token stay on this Vision Pro.")
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Gallery URL")
                    .font(.headline)
                TextField("http://192.168.1.10:8181", text: $baseURL)
                    .textContentType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .accessibilityIdentifier("connection.baseURL")
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("API token")
                    .font(.headline)
                HStack(spacing: 12) {
                    SecureField("cgpat_…", text: $token)
                        .textContentType(.password)
                        .accessibilityIdentifier("connection.token")
                    Button("Paste") {
                        if let pasted = UIPasteboard.general.string {
                            token = pasted
                        }
                    }
                    .buttonStyle(.bordered)
                    .accessibilityHint("Pastes an API token from the clipboard")
                }
            }

            connectionStatus

            HStack {
                if model.activeProfile != nil {
                    Button("Cancel") {
                        dismissWindow(id: SceneID.connection)
                    }
                    .disabled(isWorking)
                }
                Spacer()
                Button {
                    attemptConnection()
                } label: {
                    if isWorking {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text("Connect")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(baseURL.isEmpty || token.isEmpty || isWorking)
                .accessibilityIdentifier("connection.connect")
            }
        }
        .padding(32)
        .frame(width: 560)
        .onAppear {
            guard !didPopulateURL else { return }
            didPopulateURL = true
            baseURL = model.activeProfile?.baseURL.absoluteString ?? ""
        }
        .alert("Unencrypted local connection", isPresented: $showHTTPWarning) {
            Button("Connect on Trusted LAN") {
                performConnection()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("HTTP does not encrypt your token or media. Continue only on a network you trust.")
        }
    }

    @ViewBuilder
    private var connectionStatus: some View {
        switch model.connectionPhase {
        case .connecting(let step):
            Label(step.title, systemImage: "network")
                .foregroundStyle(.secondary)
                .accessibilityLabel(step.title)
        case .requiresAuthentication(let message):
            Label(message, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        default:
            EmptyView()
        }
    }

    private func attemptConnection() {
        guard let normalized = try? BaseURLNormalizer.normalize(baseURL) else {
            performConnection()
            return
        }
        if normalized.scheme?.lowercased() == "http" {
            showHTTPWarning = true
        } else {
            performConnection()
        }
    }

    private func performConnection() {
        Task {
            if await model.connect(baseURL: baseURL, token: token) {
                token = ""
                dismissWindow(id: SceneID.connection)
            }
        }
    }
}
