import SwiftUI

struct RootView: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        Group {
            if environment.isConnected {
                TabView(selection: Bindable(environment).selectedTab) {
                    LibraryView(
                        apiClient: environment.apiClient,
                        mediaRepository: environment.mediaRepository
                    )
                        .tabItem { Label("Library", systemImage: "photo.on.rectangle") }
                        .tag(AppEnvironment.Tab.library)

                    ReviewHomeView(apiClient: environment.apiClient)
                        .tabItem { Label("Review", systemImage: "checklist") }
                        .tag(AppEnvironment.Tab.review)

                    SettingsView(
                        connectionService: environment.connectionService,
                        mediaRepository: environment.mediaRepository
                    )
                        .tabItem { Label("Settings", systemImage: "gear") }
                        .tag(AppEnvironment.Tab.settings)
                }
            } else {
                ConnectionView(environment: environment)
            }
        }
    }
}
