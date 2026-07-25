import SwiftUI

@main
struct ComfyGalleryMobileApp: App {
    @State private var environment = AppEnvironment()

    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
        }
        .onChange(of: scenePhase) { _, newPhase in
            environment.handleScenePhase(newPhase)
        }
    }
}
