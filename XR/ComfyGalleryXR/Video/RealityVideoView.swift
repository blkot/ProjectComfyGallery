import AVFoundation
import RealityKit
import SwiftUI

enum RealityVideoViewingMode: Equatable, Sendable {
    case monoScreen
    case spatialPortal
}

enum RealityVideoPresentationPolicy {
    static func mode(
        for representation: VideoPlaybackRepresentation
    ) -> RealityVideoViewingMode {
        representation.isSpatial ? .spatialPortal : .monoScreen
    }
}

enum RealityVideoPresentationScaler {
    static func scale(
        presentationSize: SIMD2<Float>,
        availableSize: SIMD2<Float>
    ) -> SIMD3<Float> {
        guard
            presentationSize.x.isFinite,
            presentationSize.y.isFinite,
            presentationSize.x > 0,
            presentationSize.y > 0,
            availableSize.x.isFinite,
            availableSize.y.isFinite,
            availableSize.x > 0,
            availableSize.y > 0
        else {
            return .one
        }
        let uniformScale = min(
            availableSize.x / presentationSize.x,
            availableSize.y / presentationSize.y
        )
        return SIMD3(repeating: max(0.001, uniformScale))
    }
}

@MainActor
final class RealityVideoPresentationController {
    let entity = Entity()

    private var playerIdentity: ObjectIdentifier?
    private var itemGeneration: Int?
    private var mode: RealityVideoViewingMode?
    private var renderingStatusSubscription: EventSubscription?

    @discardableResult
    func configure(
        player: AVPlayer,
        itemGeneration: Int,
        representation: VideoPlaybackRepresentation
    ) -> Bool {
        let requestedMode = RealityVideoPresentationPolicy.mode(for: representation)
        let playerIdentity = ObjectIdentifier(player)
        guard
            self.playerIdentity != playerIdentity
                || self.itemGeneration != itemGeneration
                || mode != requestedMode
        else {
            return false
        }

        var component = VideoPlayerComponent(avPlayer: player)
        switch requestedMode {
        case .monoScreen:
            component.desiredViewingMode = .mono
            component.desiredSpatialVideoMode = .screen
        case .spatialPortal:
            component.desiredViewingMode = .stereo
            component.desiredSpatialVideoMode = .spatial
            component.desiredImmersiveViewingMode = .portal
        }
        entity.components.set(component)
        self.playerIdentity = playerIdentity
        self.itemGeneration = itemGeneration
        mode = requestedMode
        return true
    }

    func observeRenderingStatus(
        using content: RealityViewContent,
        playbackController: PlayerController,
        itemGeneration: Int
    ) {
        renderingStatusSubscription?.cancel()
        renderingStatusSubscription = content.subscribe(
            to: VideoPlayerEvents.RenderingStatusDidChange.self,
            on: entity
        ) { [weak playbackController] event in
            playbackController?.updateVideoRenderingReadiness(
                isReady: event.currentStatus == .ready,
                itemGeneration: itemGeneration
            )
        }
    }

    func fit(
        presentationSize: SIMD2<Float>,
        availableSize: SIMD2<Float>
    ) {
        entity.scale = RealityVideoPresentationScaler.scale(
            presentationSize: presentationSize,
            availableSize: availableSize
        )
        let position = entity.position(relativeTo: nil)
        entity.setPosition(SIMD3(position.x, position.y, 0), relativeTo: nil)
    }

    func clear() {
        renderingStatusSubscription?.cancel()
        renderingStatusSubscription = nil
        entity.components.remove(VideoPlayerComponent.self)
        playerIdentity = nil
        itemGeneration = nil
        mode = nil
    }
}

struct RealityVideoView: View {
    let presentationController: RealityVideoPresentationController
    let playbackController: PlayerController
    let representation: VideoPlaybackRepresentation

    var body: some View {
        GeometryReader3D { proxy in
            RealityView { content in
                content.add(presentationController.entity)
                configureAndFit(using: content, proxy: proxy)
            } update: { content in
                configureAndFit(using: content, proxy: proxy)
            }
        }
        .onDisappear {
            playbackController.updateVideoRenderingReadiness(
                isReady: false,
                itemGeneration: playbackController.itemGeneration
            )
            presentationController.clear()
        }
    }

    private func configureAndFit(
        using content: RealityViewContent,
        proxy: GeometryProxy3D
    ) {
        guard let player = playbackController.player else { return }
        let didReplaceComponent = presentationController.configure(
            player: player,
            itemGeneration: playbackController.itemGeneration,
            representation: representation
        )
        if didReplaceComponent {
            playbackController.updateVideoRenderingReadiness(
                isReady: false,
                itemGeneration: playbackController.itemGeneration
            )
            presentationController.observeRenderingStatus(
                using: content,
                playbackController: playbackController,
                itemGeneration: playbackController.itemGeneration
            )
        }

        if let renderingStatus = presentationController
            .entity
            .observable
            .components[VideoPlayerComponent.self]?
            .currentRenderingStatus {
            playbackController.updateVideoRenderingReadiness(
                isReady: renderingStatus == .ready,
                itemGeneration: playbackController.itemGeneration
            )
        }

        guard
            let presentationSize = presentationController
                .entity
                .observable
                .components[VideoPlayerComponent.self]?
                .playerScreenSize,
            presentationSize != .zero
        else {
            return
        }
        let bounds = content.convert(
            proxy.frame(in: .local),
            from: .local,
            to: .scene
        )
        presentationController.fit(
            presentationSize: presentationSize,
            availableSize: SIMD2(
                max(0.001, bounds.extents.x),
                max(0.001, bounds.extents.y)
            )
        )
    }
}
