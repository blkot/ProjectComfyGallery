import SwiftData
import SwiftUI

@main
struct ComfyGalleryXRApp: App {
    private let modelContainer: ModelContainer
    @State private var model: AppModel

    init() {
        do {
            let container = try PersistenceFactory.makeContainer()
            modelContainer = container
            let environment = try AppEnvironment(container: container)
            _model = State(initialValue: AppModel(environment: environment))
        } catch {
            fatalError("Unable to initialize local app storage.")
        }
    }

    var body: some Scene {
        Window("Gallery", id: SceneID.library) {
            LibraryView()
                .environment(model)
                .modelContainer(modelContainer)
        }
        .defaultSize(width: 1_180, height: 760)
        .windowResizability(.contentMinSize)
        .restorationBehavior(.automatic)

        Window("Media", id: SceneID.viewer) {
            MediaViewerView()
                .environment(model)
                .modelContainer(modelContainer)
        }
        .defaultSize(width: 900, height: 700)
        .windowResizability(.contentMinSize)
        .windowStyle(.plain)
        .restorationBehavior(.automatic)
        .defaultLaunchBehavior(.suppressed)
        .defaultWindowPlacement { _, context in
            if let library = context.windows.first(where: { $0.id == SceneID.library }) {
                WindowPlacement(.trailing(library))
            } else {
                WindowPlacement()
            }
        }

        Window("Connect", id: SceneID.connection) {
            ConnectionView()
                .environment(model)
                .modelContainer(modelContainer)
        }
        .defaultSize(width: 560, height: 430)
        .windowResizability(.contentSize)
        .restorationBehavior(.disabled)
        .defaultLaunchBehavior(.suppressed)
    }
}
