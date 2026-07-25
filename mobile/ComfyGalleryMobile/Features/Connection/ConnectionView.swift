import SwiftUI

struct ConnectionView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: ConnectionFeature

    init(environment: AppEnvironment) {
        _feature = State(initialValue: ConnectionFeature(
            connectionService: environment.connectionService,
            environment: environment
        ))
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    Spacer().frame(height: 40)

                    Image(systemName: "photo.on.rectangle.angled")
                        .font(.system(size: 60))
                        .foregroundStyle(.tint)
                        .padding(.bottom, 8)

                    Text("Comfy Gallery")
                        .font(.largeTitle)
                        .fontWeight(.bold)

                    Text("Connect to your self-hosted gallery server")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    VStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Server URL")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            TextField("http://192.168.50.68:8181", text: $feature.serverURL)
                                .textFieldStyle(.roundedBorder)
                                .keyboardType(.URL)
                                .autocapitalization(.none)
                                .disableAutocorrection(true)
                        }

                        VStack(alignment: .leading, spacing: 6) {
                            Text("API Token")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            SecureField("cgpat_...", text: $feature.apiToken)
                                .textFieldStyle(.roundedBorder)
                        }

                        Button {
                            Task { await feature.connect() }
                        } label: {
                            HStack {
                                if feature.isConnecting {
                                    ProgressView()
                                }
                                Text("Connect")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(feature.isConnecting)

                        Button {
                            Task { await feature.pasteTokenAndConnect() }
                        } label: {
                            Label("Paste API Token & Connect", systemImage: "doc.on.clipboard")
                        }
                        .buttonStyle(.bordered)
                    }

                    if let error = feature.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                            .multilineTextAlignment(.center)
                    }

                    connectionStateView
                }
                .padding(.horizontal, 24)
            }
            .alert("Unencrypted Connection", isPresented: $feature.showHTTPWarning) {
                Button("Connect Anyway") {
                    Task { await feature.confirmHTTP() }
                }
                Button("Cancel", role: .cancel) {
                    feature.cancelHTTP()
                }
            } message: {
                Text("HTTP connections on your local network are not encrypted. Credentials and media may be visible to other devices on the same network.")
            }
        }
    }

    @ViewBuilder
    private var connectionStateView: some View {
        switch environment.connectionService.connectionState {
        case .checkingServer:
            HStack(spacing: 8) {
                ProgressView()
                Text("Checking server...")
            }
            .foregroundStyle(.secondary)
        case .serverFound:
            Label("Server found", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .authenticationRequired:
            Label("Authentication required", systemImage: "lock.fill")
                .foregroundStyle(.orange)
        case .authenticating:
            HStack(spacing: 8) {
                ProgressView()
                Text("Authenticating...")
            }
            .foregroundStyle(.secondary)
        case .connected(let session):
            Label("Connected as \(session.user.username)", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .error:
            EmptyView()
        case .disconnected:
            EmptyView()
        }
    }
}
