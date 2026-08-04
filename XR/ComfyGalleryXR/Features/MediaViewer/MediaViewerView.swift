import SwiftUI

enum VideoSurfaceLayerPolicy {
    static func showsPreview(hasPlayer: Bool) -> Bool {
        !hasPlayer
    }
}

struct MediaViewerView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    @GestureState private var dragOffset: CGFloat = 0
    @State private var showSpatialExplanation = false
    @AppStorage("hasExplainedSpatialGeneration") private var hasExplainedSpatialGeneration = false

    var body: some View {
        VStack(spacing: 0) {
            GeometryReader { proxy in
                ZStack {
                    if !model.spatial.hasPresentationComponent {
                        Color.black.opacity(0.82)
                    }
                    viewerContent
                        .offset(x: reduceMotion ? 0 : dragOffset * 0.28)
                        .animation(
                            reduceMotion ? .easeOut(duration: 0.12) : .spring(response: 0.28),
                            value: dragOffset
                        )
                }
                .contentShape(Rectangle())
                .highPriorityGesture(
                    navigationGesture(cardWidth: proxy.size.width),
                    including: gestureMask
                )
                .clipped()
            }

            if model.viewer.selection != nil {
                Divider()
                viewerControls
            }
        }
        .frame(minWidth: 480, minHeight: 360)
        .task {
            await model.bootstrap()
            if model.connectionPhase.needsConnectionWindow {
                openWindow(id: SceneID.connection)
            }
        }
        .onChange(of: model.connectionPhase) {
            if model.connectionPhase.needsConnectionWindow {
                openWindow(id: SceneID.connection)
            }
        }
        .onChange(of: scenePhase) {
            model.viewerScenePhaseChanged(isActive: scenePhase == .active)
        }
        .onDisappear {
            model.closeViewer()
        }
        .alert("Make this image spatial?", isPresented: $showSpatialExplanation) {
            Button("Make Spatial") {
                hasExplainedSpatialGeneration = true
                model.makeSpatial()
            }
            Button("Not Now", role: .cancel) {}
        } message: {
            Text("Depth is generated on this Vision Pro and may contain artifacts. Your original gallery image is never changed.")
        }
    }

    @ViewBuilder
    private var viewerContent: some View {
        switch model.viewer.loadState {
        case .empty:
            ContentUnavailableView(
                "No Media Selected",
                systemImage: "photo",
                description: Text("Choose an item in the Gallery window.")
            )
            .foregroundStyle(.white)
        case .unavailable(let message):
            unavailableView(message)
        case .failed(let message):
            unavailableView(message)
        default:
            mediaSurface
        }
    }

    @ViewBuilder
    private var mediaSurface: some View {
        if model.spatial.hasPresentationComponent {
            SpatialImageView(controller: model.spatial)
                // ImagePresentationComponent does not need direct taps. Let the
                // parent media region receive look-pinch-drag navigation.
                .allowsHitTesting(false)

            if model.spatial.state == .spatial && !model.spatial.isPresentationReady {
                ProgressView("Activating Spatial…")
                    .tint(.white)
                    .foregroundStyle(.white)
                    .padding()
                    .background(.ultraThinMaterial, in: Capsule())
            }
        } else if model.viewer.detail?.kind == .video {
            ZStack {
                if
                    VideoSurfaceLayerPolicy.showsPreview(
                        hasPlayer: model.player.player != nil
                    ),
                    let image = model.viewer.image
                {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .accessibilityLabel(mediaAccessibilityLabel)
                }
                if let player = model.player.player {
                    PlayerViewControllerRepresentable(
                        player: player,
                        presentation: model.player.presentation,
                        shouldAutoplay: model.player.shouldAutoplay,
                        isActive: model.player.isActive
                    )
                        .accessibilityLabel(mediaAccessibilityLabel)
                }
                if model.viewer.videoIsPreparing || model.viewer.image == nil {
                    ProgressView("Preparing video…")
                        .tint(.white)
                        .foregroundStyle(.white)
                        .padding()
                        .background(.ultraThinMaterial, in: Capsule())
                }
                if let message = model.viewer.videoPlaybackError {
                    VStack {
                        Spacer()
                        Label(message, systemImage: "exclamationmark.triangle")
                            .font(.callout)
                            .padding(12)
                            .background(.regularMaterial, in: Capsule())
                            .padding(.bottom, 20)
                    }
                }
            }
        } else if let image = model.viewer.image {
            Image(uiImage: image)
                .resizable()
                .scaledToFit()
                .accessibilityLabel(mediaAccessibilityLabel)
                .transition(.opacity)
        } else {
            ProgressView("Loading media…")
                .tint(.white)
                .foregroundStyle(.white)
        }

        if model.spatial.state == .generating {
            ProgressView("Making Spatial…")
                .tint(.white)
                .foregroundStyle(.white)
                .padding()
                .background(.ultraThinMaterial, in: Capsule())
        }

        if case .failed(let message) = model.spatial.state {
            VStack {
                Spacer()
                Label(message, systemImage: "exclamationmark.triangle")
                    .font(.callout)
                    .padding(12)
                    .background(.regularMaterial, in: Capsule())
                    .padding(.bottom, 34)
            }
            .transition(.opacity)
        }
    }

    private func unavailableView(_ message: String) -> some View {
        ContentUnavailableView {
            Label("Media Unavailable", systemImage: "photo.badge.exclamationmark")
        } description: {
            Text(message)
        } actions: {
            Button("Retry") {
                model.retryViewer()
            }
        }
        .foregroundStyle(.white)
    }

    private var viewerControls: some View {
        VStack(spacing: 8) {
            ViewThatFits(in: .horizontal) {
                controlRow(compact: false)
                controlRow(compact: true)
            }

            if
                let mediaID = model.viewer.detail?.id,
                let message = model.preferenceSyncError(mediaID: mediaID)
            {
                HStack(spacing: 10) {
                    Label(message, systemImage: "arrow.triangle.2.circlepath")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                    Spacer(minLength: 8)
                    Button("Retry") {
                        model.retryPreferenceSyncForCurrentMedia()
                    }
                    .disabled(model.isPreferenceSyncing(mediaID: mediaID))
                }
            }
        }
        .buttonStyle(.borderless)
        .padding(.horizontal, 18)
        .padding(.vertical, 8)
        .background(.regularMaterial)
    }

    private func controlRow(compact: Bool) -> some View {
        HStack(spacing: compact ? 10 : 16) {
            Button {
                model.navigate(.previous)
            } label: {
                controlLabel("Previous", systemImage: "chevron.left", compact: compact)
            }
            .disabled(model.viewer.navigation?.previousID == nil)
            .keyboardShortcut(.leftArrow, modifiers: [])
            .frame(minHeight: 60)
            .accessibilityIdentifier("viewer.previous")

            Text(model.viewer.positionText)
                .font(.headline.monospacedDigit())
                .frame(minWidth: compact ? 72 : 90)
                .accessibilityLabel("Item \(model.viewer.positionText)")

            Button {
                model.navigate(.next)
            } label: {
                controlLabel("Next", systemImage: "chevron.right", compact: compact)
            }
            .disabled(model.viewer.navigation?.nextID == nil)
            .keyboardShortcut(.rightArrow, modifiers: [])
            .frame(minHeight: 60)
            .accessibilityIdentifier("viewer.next")

            if model.viewer.detail?.kind == .video {
                Button {
                    model.player.toggleLooping()
                } label: {
                    controlLabel(
                        model.player.isLooping ? "Looping" : "Loop",
                        systemImage: model.player.isLooping ? "repeat.circle.fill" : "repeat",
                        compact: compact
                    )
                }
                .frame(minHeight: 60)
                .accessibilityValue(model.player.isLooping ? "On" : "Off")
                .accessibilityIdentifier("viewer.loop")
            }

            favoriteAction(compact: compact)
            spatialAction(compact: compact)
        }
    }

    @ViewBuilder
    private func favoriteAction(compact: Bool) -> some View {
        if let detail = model.viewer.detail {
            Button {
                model.toggleFavoriteForCurrentMedia()
            } label: {
                controlLabel(
                    detail.favorite ? "Favorite" : "Add Favorite",
                    systemImage: detail.favorite ? "heart.fill" : "heart",
                    compact: compact
                )
            }
            .foregroundStyle(detail.favorite ? .pink : .primary)
            .disabled(model.isPreferenceSyncing(mediaID: detail.id))
            .frame(minHeight: 60)
            .accessibilityValue(detail.favorite ? "On" : "Off")
            .accessibilityHint("Updates the favorite flag on the gallery server.")
            .accessibilityIdentifier("viewer.favorite")
        }
    }

    @ViewBuilder
    private func spatialAction(compact: Bool) -> some View {
        if
            let mediaID = model.viewer.detail?.id,
            model.isPreferenceSyncing(mediaID: mediaID)
        {
            HStack(spacing: 10) {
                ProgressView()
                    .controlSize(.small)
                if !compact {
                    Text("Saving…")
                }
            }
            .frame(minHeight: 60)
        } else if model.viewer.detail?.kind == .video {
            videoSpatialAction(compact: compact)
        } else {
            switch model.spatial.state {
            case .unavailable:
                EmptyView()
            case .generating:
                HStack(spacing: 10) {
                    ProgressView()
                        .controlSize(.small)
                    if !compact {
                        Text("Making Spatial…")
                    }
                    Button("Cancel") {
                        model.cancelSpatial()
                    }
                }
                .frame(minHeight: 60)
            case .spatial:
                Button {
                    model.disableSpatial()
                } label: {
                    controlLabel(
                        "Disable Spatial",
                        systemImage: "cube.transparent",
                        compact: compact
                    )
                }
                .frame(minHeight: 60)
                .accessibilityIdentifier("viewer.disableSpatial")
            case .ready2D where model.spatial.hasGenerated:
                Button {
                    model.enableCachedSpatial()
                } label: {
                    controlLabel(
                        "Enable Spatial",
                        systemImage: "cube.transparent.fill",
                        compact: compact
                    )
                }
                .frame(minHeight: 60)
                .accessibilityIdentifier("viewer.enableSpatial")
            case .ready2D, .failed:
                Button {
                    if hasExplainedSpatialGeneration {
                        model.makeSpatial()
                    } else {
                        showSpatialExplanation = true
                    }
                } label: {
                    controlLabel(
                        "Make Spatial",
                        systemImage: "wand.and.sparkles",
                        compact: compact
                    )
                }
                .frame(minHeight: 60)
                .accessibilityIdentifier("viewer.makeSpatial")
            }
        }
    }

    @ViewBuilder
    private func videoSpatialAction(compact: Bool) -> some View {
        if let detail = model.viewer.detail {
            if detail.prefersSpatialPlayback {
                Button {
                    model.toggleSpatialPlaybackForCurrentVideo()
                } label: {
                    controlLabel(
                        detail.activeSpatialVideoVariant == nil
                            ? "Disable Spatial Preference"
                            : "Play in 2D",
                        systemImage: "rectangle",
                        compact: compact
                    )
                }
                .frame(minHeight: 60)
                .accessibilityHint(
                    detail.activeSpatialVideoVariant == nil
                        ? "The spatial variant is unavailable, so ordinary video is playing."
                        : "Switches this media to its ordinary video."
                )
                .accessibilityIdentifier("viewer.disableSpatialVideo")
            } else if detail.activeSpatialVideoVariant != nil {
                Button {
                    model.toggleSpatialPlaybackForCurrentVideo()
                } label: {
                    controlLabel(
                        "Play Spatial",
                        systemImage: "cube.transparent.fill",
                        compact: compact
                    )
                }
                .frame(minHeight: 60)
                .accessibilityHint("Switches this media to its spatial video variant.")
                .accessibilityIdentifier("viewer.enableSpatialVideo")
            }
        }
    }

    @ViewBuilder
    private func controlLabel(
        _ title: String,
        systemImage: String,
        compact: Bool
    ) -> some View {
        if compact {
            Image(systemName: systemImage)
                .accessibilityLabel(title)
        } else {
            Label(title, systemImage: systemImage)
        }
    }

    private var gestureMask: GestureMask {
        model.viewer.detail?.kind == .video ? .none : .all
    }

    private func navigationGesture(cardWidth: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: 16)
            .updating($dragOffset) { value, state, _ in
                guard abs(value.translation.width) > abs(value.translation.height) else { return }
                state = value.translation.width
            }
            .onEnded { value in
                guard let direction = DragNavigationDecision.direction(
                    translation: value.translation,
                    predictedEndTranslation: value.predictedEndTranslation,
                    cardWidth: cardWidth
                ) else {
                    return
                }
                switch direction {
                case .previous where model.viewer.navigation?.previousID != nil:
                    model.navigate(.previous)
                case .next where model.viewer.navigation?.nextID != nil:
                    model.navigate(.next)
                default:
                    break
                }
            }
    }

    private var mediaAccessibilityLabel: String {
        let kind = model.viewer.detail?.kind == .video ? "Video" : "Image"
        if let navigation = model.viewer.navigation {
            return "\(kind), item \(navigation.position) of \(navigation.total)"
        }
        return kind
    }
}
