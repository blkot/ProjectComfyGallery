import AVFoundation
import AVKit
import SwiftUI

enum VideoPlaybackPresentation: Equatable, Sendable {
    case embedded
    case expandedSpatial
}

@MainActor
protocol VideoPlaybackControlling: AnyObject {
    func play()
    func pause()
}

extension AVPlayer: VideoPlaybackControlling {}

@MainActor
protocol VideoPlaybackExperienceTransitioning: AnyObject {
    var currentPresentation: VideoPlaybackPresentation { get }

    func transition(to presentation: VideoPlaybackPresentation) async -> Bool
}

@MainActor
final class VideoPlaybackExperienceCoordinator {
    private weak var experience: (any VideoPlaybackExperienceTransitioning)?
    private weak var player: (any VideoPlaybackControlling)?
    private var playerIdentifier: ObjectIdentifier?
    private var desiredPresentation: VideoPlaybackPresentation = .embedded
    private var shouldAutoplay = false
    private var isActive = false
    private var viewIsVisible = false
    private var presentationIsReady = false
    private var requestGeneration = 0
    private var reconciliationTask: Task<Void, Never>?

    init(experience: any VideoPlaybackExperienceTransitioning) {
        self.experience = experience
    }

    func update(
        player: (any VideoPlaybackControlling)?,
        presentation: VideoPlaybackPresentation,
        shouldAutoplay: Bool,
        isActive: Bool
    ) {
        let nextIdentifier = player.map(ObjectIdentifier.init)
        let requestChanged =
            nextIdentifier != playerIdentifier
            || presentation != desiredPresentation

        self.player = player
        playerIdentifier = nextIdentifier
        desiredPresentation = presentation
        self.shouldAutoplay = shouldAutoplay
        self.isActive = isActive

        if requestChanged {
            requestGeneration += 1
            presentationIsReady = false
            player?.pause()
            startReconciliationIfNeeded()
        } else {
            applyPlaybackPolicy()
        }
    }

    func setViewVisible(_ isVisible: Bool) {
        guard viewIsVisible != isVisible else { return }
        viewIsVisible = isVisible
        if isVisible {
            startReconciliationIfNeeded()
        } else {
            requestGeneration += 1
            presentationIsReady = false
            reconciliationTask?.cancel()
            reconciliationTask = nil
            player?.pause()
        }
    }

    func experienceDidChange() {
        guard
            let experience,
            experience.currentPresentation == desiredPresentation,
            viewIsVisible
        else {
            presentationIsReady = false
            player?.pause()
            return
        }
        presentationIsReady = true
        applyPlaybackPolicy()
    }

    func stop() {
        requestGeneration += 1
        presentationIsReady = false
        reconciliationTask?.cancel()
        reconciliationTask = nil
        player?.pause()
        player = nil
        playerIdentifier = nil
    }

    private func startReconciliationIfNeeded() {
        guard
            viewIsVisible,
            player != nil,
            reconciliationTask == nil
        else {
            return
        }

        reconciliationTask = Task { [weak self] in
            guard let self else { return }
            await self.reconcilePresentation()
        }
    }

    private func reconcilePresentation() async {
        defer { reconciliationTask = nil }

        while
            !Task.isCancelled,
            viewIsVisible,
            player != nil,
            let experience
        {
            let generation = requestGeneration
            let requestedPresentation = desiredPresentation

            if experience.currentPresentation == requestedPresentation {
                guard generation == requestGeneration else { continue }
                presentationIsReady = true
                applyPlaybackPolicy()
                return
            }

            let completed = await experience.transition(to: requestedPresentation)
            guard !Task.isCancelled else { return }

            // A source or preference switch may arrive while AVKit is still
            // transitioning. Finish serially, then reconcile to the newest target
            // without ever starting the stale player.
            guard generation == requestGeneration else { continue }
            guard
                completed,
                experience.currentPresentation == requestedPresentation
            else {
                presentationIsReady = false
                player?.pause()
                return
            }

            presentationIsReady = true
            applyPlaybackPolicy()
            return
        }
    }

    private func applyPlaybackPolicy() {
        guard
            let player,
            presentationIsReady,
            viewIsVisible,
            shouldAutoplay,
            isActive
        else {
            player?.pause()
            return
        }
        player.play()
    }
}

struct PlayerViewControllerRepresentable: UIViewControllerRepresentable {
    let player: AVPlayer?
    let presentation: VideoPlaybackPresentation
    let shouldAutoplay: Bool
    let isActive: Bool

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIViewController(context: Context) -> AVPlayerViewController {
        let controller = PlayerViewController()
        controller.player = player
        controller.showsPlaybackControls = true
        controller.requiresMonoscopicViewingMode = false
        controller.onViewDidAppear = { [weak coordinator = context.coordinator] in
            coordinator?.setViewVisible(true)
        }
        context.coordinator.attach(to: controller)
        context.coordinator.update(
            player: player,
            presentation: presentation,
            shouldAutoplay: shouldAutoplay,
            isActive: isActive
        )
        return controller
    }

    func updateUIViewController(_ controller: AVPlayerViewController, context: Context) {
        controller.requiresMonoscopicViewingMode = false
        if controller.player !== player {
            controller.player = player
        }
        context.coordinator.update(
            player: player,
            presentation: presentation,
            shouldAutoplay: shouldAutoplay,
            isActive: isActive
        )
    }

    static func dismantleUIViewController(
        _ controller: AVPlayerViewController,
        coordinator: Coordinator
    ) {
        coordinator.dismantle(controller)
    }

    @MainActor
    final class Coordinator: NSObject,
        VideoPlaybackExperienceTransitioning,
        AVExperienceController.Delegate
    {
        private weak var controller: AVPlayerViewController?
        private lazy var playbackExperience =
            VideoPlaybackExperienceCoordinator(experience: self)

        var currentPresentation: VideoPlaybackPresentation {
            guard let controller else { return .embedded }
            switch controller.experienceController.experience {
            case .expanded, .immersive:
                return .expandedSpatial
            case .embedded, .multiview:
                return .embedded
            @unknown default:
                return .embedded
            }
        }

        func attach(to controller: AVPlayerViewController) {
            self.controller = controller
            controller.experienceController.allowedExperiences = .recommended()
            controller.experienceController.delegate = self
        }

        func update(
            player: AVPlayer?,
            presentation: VideoPlaybackPresentation,
            shouldAutoplay: Bool,
            isActive: Bool
        ) {
            playbackExperience.update(
                player: player,
                presentation: presentation,
                shouldAutoplay: shouldAutoplay,
                isActive: isActive
            )
        }

        func setViewVisible(_ isVisible: Bool) {
            playbackExperience.setViewVisible(isVisible)
        }

        func transition(to presentation: VideoPlaybackPresentation) async -> Bool {
            guard let controller else { return false }
            let target: AVExperienceController.Experience =
                presentation == .expandedSpatial ? .expanded : .embedded
            switch await controller.experienceController.transition(to: target) {
            case .completed:
                return true
            case .reversed:
                return false
            @unknown default:
                return false
            }
        }

        func dismantle(_ controller: AVPlayerViewController) {
            playbackExperience.stop()
            controller.experienceController.delegate = nil
            controller.player?.pause()
            controller.player = nil
            self.controller = nil

            Task {
                _ = await controller.experienceController.transition(to: .embedded)
            }
        }

        func experienceController(
            _ controller: AVExperienceController,
            prepareForTransitionUsing context: AVExperienceController.TransitionContext
        ) async {
            guard context.toExperience == .expanded else { return }
            if let scene = self.controller?.view.window?.windowScene {
                controller.configuration.placement = .over(scene: scene)
            } else {
                controller.configuration.placement = .unspecified
            }
            controller.configuration.expanded.automaticTransitionToImmersive = .none
        }

        func experienceController(
            _ controller: AVExperienceController,
            didChangeTransitionContext context: AVExperienceController.TransitionContext
        ) {
            guard case .finished(result: .completed) = context.status else { return }
            playbackExperience.experienceDidChange()
        }

        func experienceController(
            _ controller: AVExperienceController,
            didChangeAvailableExperiences availableExperiences: AVExperienceController.Experiences
        ) {}
    }

    private final class PlayerViewController: AVPlayerViewController {
        var onViewDidAppear: (() -> Void)?

        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            onViewDidAppear?()
        }
    }
}
