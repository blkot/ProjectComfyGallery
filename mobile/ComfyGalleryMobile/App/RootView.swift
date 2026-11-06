import SwiftUI

struct RootView: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        if environment.isConnected {
            TabView(selection: Bindable(environment).selectedTab) {
                LibraryView(apiClient: environment.apiClient, tab: .library)
                    .tabItem { Label("图库", systemImage: "photo.on.rectangle") }.tag(AppEnvironment.Tab.library)
                PromptRegistryView(apiClient: environment.apiClient)
                    .tabItem { Label("词库", systemImage: "text.book.closed") }.tag(AppEnvironment.Tab.registry)
                LibraryView(apiClient: environment.apiClient, tab: .search)
                    .tabItem { Label("搜索", systemImage: "magnifyingglass") }.tag(AppEnvironment.Tab.search)
            }
        } else {
            ConnectionView(environment: environment)
        }
    }
}
