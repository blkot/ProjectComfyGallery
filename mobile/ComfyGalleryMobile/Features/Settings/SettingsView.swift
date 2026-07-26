import SwiftUI

struct SettingsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: SettingsFeature

    init(connectionService: ConnectionService, mediaRepository: MediaRepository) {
        _feature = State(initialValue: SettingsFeature(
            connectionService: connectionService,
            mediaRepository: mediaRepository
        ))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Connection") {
                    if case .connected(let session) = environment.connectionService.connectionState {
                        HStack {
                            Label("Connected as", systemImage: "person.fill")
                            Spacer()
                            Text(session.user.username).foregroundStyle(.secondary)
                        }
                    }

                    if let url = environment.connectionService.baseURL {
                        HStack {
                            Label("Server", systemImage: "network")
                            Spacer()
                            Text(url.absoluteString).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                        }
                    }

                    if let version = environment.connectionService.serverVersion {
                        HStack {
                            Label("Version", systemImage: "info.circle")
                            Spacer()
                            Text(version).foregroundStyle(.secondary)
                        }
                    }

                    Button("Disconnect", role: .destructive) {
                        feature.showDisconnectConfirmation = true
                    }
                }

                Section("Privacy") {
                    Toggle("Privacy Cover in App Switcher", isOn: $feature.privacyCoverEnabled)
                }

                Section("Cache") {
                    HStack {
                        Text("Cache Size")
                        Spacer()
                        Text(feature.cacheSizeDescription).foregroundStyle(.secondary)
                    }

                    Button("Clear Cache") {
                        Task { await feature.clearCache() }
                    }
                    .disabled(feature.isClearingCache)
                }

                Section("About") {
                    HStack {
                        Text("App Version")
                        Spacer()
                        Text(feature.appVersionDescription).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .alert("Disconnect", isPresented: $feature.showDisconnectConfirmation) {
                Button("Disconnect", role: .destructive) {
                    Task { await feature.disconnect() }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will erase your saved token, pending changes, and cached media.")
            }
            .task {
                await feature.refreshCacheSize()
            }
        }
    }
}
