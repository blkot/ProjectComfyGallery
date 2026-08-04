import SwiftUI
import UIKit

struct LibraryView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow
    @Environment(\.scenePhase) private var scenePhase

    @State private var scrollPosition = ScrollPosition(idType: UUID.self)
    @State private var showDisconnectConfirmation = false

    private let columns = [
        GridItem(.adaptive(minimum: 180, maximum: 240), spacing: 16)
    ]

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            content
        }
        .frame(minWidth: 720, minHeight: 520)
        .ornament(attachmentAnchor: .scene(.bottom)) {
            if model.connectionPhase.isUsable {
                libraryOrnament
            }
        }
        .task {
            await model.bootstrap()
            openConnectionIfNeeded()
        }
        .onChange(of: model.connectionPhase) {
            openConnectionIfNeeded()
        }
        .onChange(of: scrollPosition) {
            guard scrollPosition.isPositionedByUser else { return }
            model.updateScrollAnchor(scrollPosition.viewID(type: UUID.self))
        }
        .onChange(of: scenePhase) {
            model.libraryScenePhaseChanged(isActive: scenePhase == .active)
        }
        .onReceive(NotificationCenter.default.publisher(
            for: UIApplication.didReceiveMemoryWarningNotification
        )) { _ in
            model.handleMemoryPressure()
        }
        .confirmationDialog(
            "Disconnect from this gallery?",
            isPresented: $showDisconnectConfirmation,
            titleVisibility: .visible
        ) {
            Button("Disconnect and Clear Cache", role: .destructive) {
                Task { await model.disconnect() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("The saved token and locally cached media will be removed.")
        }
    }

    private var header: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Gallery")
                    .font(.largeTitle.bold())
                Text(countText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if model.connectionPhase == .offline {
                Label("Offline", systemImage: "wifi.slash")
                    .foregroundStyle(.orange)
            }
            Button {
                Task { await model.refreshLibrary() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            .disabled(!model.connectionPhase.isUsable)
            .hoverEffect()
            .accessibilityIdentifier("library.refresh")

            Menu {
                Button("Reconnect") {
                    model.hasPresentedConnection = true
                    openWindow(id: SceneID.connection)
                }
                Divider()
                Button("Disconnect…", role: .destructive) {
                    showDisconnectConfirmation = true
                }
            } label: {
                Label("Connection", systemImage: "ellipsis.circle")
                    .labelStyle(.iconOnly)
            }
            .disabled(model.activeProfile == nil)
            .hoverEffect()
        }
        .padding(.horizontal, 28)
        .padding(.vertical, 18)
    }

    @ViewBuilder
    private var content: some View {
        switch model.connectionPhase {
        case .bootstrapping:
            ProgressView("Restoring Gallery…")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .disconnected, .requiresAuthentication:
            ContentUnavailableView {
                Label("Connect to Gallery", systemImage: "rectangle.connected.to.line.below")
            } description: {
                Text("Enter the gallery URL and an API token to browse media.")
            } actions: {
                Button("Connect") {
                    model.hasPresentedConnection = true
                    openWindow(id: SceneID.connection)
                }
                .buttonStyle(.borderedProminent)
            }
        default:
            libraryContent
        }
    }

    @ViewBuilder
    private var libraryContent: some View {
        switch model.library.loadState {
        case .initialLoading where model.library.items.isEmpty:
            skeletonGrid
        case .failedInitial(let message):
            ContentUnavailableView {
                Label("Couldn’t Load Gallery", systemImage: "exclamationmark.triangle")
            } description: {
                Text(message)
            } actions: {
                Button("Retry") {
                    Task { await model.refreshLibrary() }
                }
            }
        case .exhausted where model.library.items.isEmpty:
            ContentUnavailableView(
                "No Media",
                systemImage: "photo.on.rectangle.angled",
                description: Text("No media matched this view.")
            )
        default:
            grid
        }
    }

    private var grid: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 16) {
                ForEach(model.library.items) { media in
                    ZStack(alignment: .topTrailing) {
                        Button {
                            model.updateScrollAnchor(media.id)
                            model.select(media)
                            openWindow(id: SceneID.viewer)
                        } label: {
                            MediaGridCell(media: media)
                        }
                        .buttonStyle(.plain)

                        Button {
                            if model.preferenceSyncError(mediaID: media.id) != nil {
                                model.retryPreferenceSync(mediaID: media.id)
                            } else {
                                model.setFavorite(!media.favorite, for: media)
                            }
                        } label: {
                            ZStack(alignment: .topTrailing) {
                                Image(systemName: media.favorite ? "heart.fill" : "heart")
                                    .font(.headline)
                                    .foregroundStyle(media.favorite ? .pink : .primary)
                                    .padding(10)
                                    .background(.regularMaterial, in: Circle())

                                if model.preferenceSyncError(mediaID: media.id) != nil {
                                    Image(systemName: "exclamationmark.circle.fill")
                                        .font(.caption2)
                                        .foregroundStyle(.orange)
                                        .background(.regularMaterial, in: Circle())
                                        .offset(x: 3, y: -3)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .disabled(model.isPreferenceSyncing(mediaID: media.id))
                        .padding(10)
                        .accessibilityLabel(
                            model.preferenceSyncError(mediaID: media.id) != nil
                                ? "Retry preference sync"
                                : (media.favorite ? "Remove from Favorites" : "Add to Favorites")
                        )
                        .accessibilityHint(
                            model.preferenceSyncError(mediaID: media.id) != nil
                                ? "Retries the pending change on the gallery server."
                                : "Updates this media on the gallery server."
                        )
                    }
                    .id(media.id)
                    .onAppear {
                        model.loadMoreIfNeeded(after: media)
                    }
                }
            }
            .scrollTargetLayout()
            .padding(24)

            pagingFooter
                .padding(.bottom, 42)
        }
        .scrollPosition($scrollPosition, anchor: .top)
        .onAppear {
            if let anchor = model.library.scrollAnchor {
                scrollPosition.scrollTo(id: anchor, anchor: .top)
            }
        }
    }

    @ViewBuilder
    private var pagingFooter: some View {
        switch model.library.loadState {
        case .loadingNext:
            ProgressView("Loading more…")
                .padding()
        case .refreshing:
            ProgressView("Refreshing…")
                .padding()
        case .failedRefresh(let message):
            VStack(spacing: 10) {
                Text(message)
                    .foregroundStyle(.secondary)
                Button("Retry Refresh") {
                    Task { await model.refreshLibrary() }
                }
            }
            .padding()
        case .failedNext(let message):
            VStack(spacing: 10) {
                Text(message)
                    .foregroundStyle(.secondary)
                Button("Retry") {
                    Task { await model.loadNextPage() }
                }
            }
            .padding()
        default:
            EmptyView()
        }
    }

    private var skeletonGrid: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 16) {
                ForEach(0..<12, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(.thinMaterial)
                        .aspectRatio(2.0 / 3.0, contentMode: .fit)
                        .overlay { ProgressView().controlSize(.small) }
                }
            }
            .padding(24)
        }
        .accessibilityLabel("Loading gallery")
    }

    private var libraryOrnament: some View {
        HStack(spacing: 18) {
            Picker("Media type", selection: kindBinding) {
                ForEach(GalleryKindFilter.allCases) { kind in
                    Text(kind.title).tag(kind)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 310)

            Picker("Saved view", selection: preferenceBinding) {
                ForEach(GalleryPreferenceFilter.allCases) { preference in
                    Label(preference.title, systemImage: preference.systemImage)
                        .tag(preference)
                }
            }
            .pickerStyle(.menu)
            .frame(minWidth: 145)

            Toggle("Include Trash", isOn: trashBinding)
                .toggleStyle(.button)

            Picker("Sort", selection: sortBinding) {
                ForEach(MediaSort.allCases) { sort in
                    Text(sort.title).tag(sort)
                }
            }
            .frame(minWidth: 170)

            connectionIndicator
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .glassBackgroundEffect()
    }

    private var connectionIndicator: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(model.connectionPhase == .offline ? .orange : .green)
                .frame(width: 9, height: 9)
            Text(model.connectionPhase == .offline ? "Offline" : "Connected")
                .font(.caption)
        }
        .accessibilityElement(children: .combine)
    }

    private var kindBinding: Binding<GalleryKindFilter> {
        Binding {
            model.library.scope.kind
        } set: { newValue in
            var scope = model.library.scope
            scope.kind = newValue
            model.updateScope(scope)
        }
    }

    private var trashBinding: Binding<Bool> {
        Binding {
            model.library.scope.includesTrash
        } set: { newValue in
            var scope = model.library.scope
            scope.includesTrash = newValue
            model.updateScope(scope)
        }
    }

    private var preferenceBinding: Binding<GalleryPreferenceFilter> {
        Binding {
            model.library.scope.preference
        } set: { newValue in
            var scope = model.library.scope
            scope.preference = newValue
            model.updateScope(scope)
        }
    }

    private var sortBinding: Binding<MediaSort> {
        Binding {
            model.library.scope.sort
        } set: { newValue in
            var scope = model.library.scope
            scope.sort = newValue
            model.updateScope(scope)
        }
    }

    private var countText: String {
        switch model.library.loadState {
        case .initialLoading: "Loading…"
        default: "\(model.library.total) items"
        }
    }

    private func openConnectionIfNeeded() {
        guard
            model.hasBootstrapped,
            model.connectionPhase.needsConnectionWindow,
            !model.hasPresentedConnection
        else {
            return
        }
        model.hasPresentedConnection = true
        openWindow(id: SceneID.connection)
    }
}
