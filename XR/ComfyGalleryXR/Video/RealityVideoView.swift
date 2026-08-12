import AVFoundation
import RealityKit
import SwiftUI

enum RealityVideoViewingMode: Equatable, Sendable {
    case monoScreen
    case spatialPortal
}

struct RealityVideoPresentationLease: Hashable {
    private let identifier = UUID()
}

struct RealityVideoPresentationOwnership: Equatable, Hashable {
    let lease: RealityVideoPresentationLease
    let itemGeneration: Int
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
    private var mode: RealityVideoViewingMode?
    private var owner: RealityVideoPresentationOwnership?
    private var renderingStatusSubscription: EventSubscription?

    @discardableResult
    func configure(
        player: AVPlayer,
        ownership: RealityVideoPresentationOwnership,
        representation: VideoPlaybackRepresentation
    ) -> Bool {
        let requestedMode = RealityVideoPresentationPolicy.mode(for: representation)
        let playerIdentity = ObjectIdentifier(player)
        guard
            self.playerIdentity != playerIdentity
                || self.owner?.itemGeneration != ownership.itemGeneration
                || mode != requestedMode
                || self.owner != ownership
        else {
            return false
        }

        if
            self.playerIdentity != playerIdentity
                || self.owner?.itemGeneration != ownership.itemGeneration
                || mode != requestedMode {
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
        }
        self.playerIdentity = playerIdentity
        mode = requestedMode
        self.owner = ownership
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

    @discardableResult
    func teardown(
        ownedBy ownership: RealityVideoPresentationOwnership,
        playbackController: PlayerController
    ) -> Bool {
        guard owner == ownership else {
            return false
        }

        renderingStatusSubscription?.cancel()
        renderingStatusSubscription = nil
        entity.components.remove(VideoPlayerComponent.self)
        playerIdentity = nil
        mode = nil
        owner = nil
        playbackController.updateVideoRenderingReadiness(
            isReady: false,
            itemGeneration: ownership.itemGeneration
        )
        return true
    }
}

struct RealityVideoView: View {
    let presentationController: RealityVideoPresentationController
    let playbackController: PlayerController
    let representation: VideoPlaybackRepresentation
    @State private var ownerLease = RealityVideoPresentationLease()

    var body: some View {
        let ownership = RealityVideoPresentationOwnership(
            lease: ownerLease,
            itemGeneration: playbackController.itemGeneration
        )
        GeometryReader3D { proxy in
            RealityView { content in
                content.add(presentationController.entity)
                configureAndFit(
                    using: content,
                    proxy: proxy,
                    ownership: ownership
                )
            } update: { content in
                configureAndFit(
                    using: content,
                    proxy: proxy,
                    ownership: ownership
                )
            }
            .id(ownership)
            .onDisappear {
                presentationController.teardown(
                    ownedBy: ownership,
                    playbackController: playbackController
                )
            }
        }
    }

    private func configureAndFit(
        using content: RealityViewContent,
        proxy: GeometryProxy3D,
        ownership: RealityVideoPresentationOwnership
    ) {
        guard
            ownership.itemGeneration == playbackController.itemGeneration,
            let player = playbackController.player
        else {
            return
        }
        let didReplaceComponent = presentationController.configure(
            player: player,
            ownership: ownership,
            representation: representation
        )
        if didReplaceComponent {
            playbackController.updateVideoRenderingReadiness(
                isReady: false,
                itemGeneration: ownership.itemGeneration
            )
            presentationController.observeRenderingStatus(
                using: content,
                playbackController: playbackController,
                itemGeneration: ownership.itemGeneration
            )
        }

        if let renderingStatus = presentationController
            .entity
            .observable
            .components[VideoPlayerComponent.self]?
            .currentRenderingStatus {
            playbackController.updateVideoRenderingReadiness(
                isReady: renderingStatus == .ready,
                itemGeneration: ownership.itemGeneration
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
