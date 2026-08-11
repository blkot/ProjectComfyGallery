import AVFoundation
import Foundation
import Observation

enum VideoPlaybackDefaults {
    static let autoplay = true
    static let looping = true
}

@MainActor
protocol VideoLoopPlaybackControlling: AnyObject {
    func play()
    func seekToStart(completion: @escaping @MainActor (Bool) -> Void)
}

extension AVPlayer: VideoLoopPlaybackControlling {
    func seekToStart(completion: @escaping @MainActor (Bool) -> Void) {
        seek(
            to: .zero,
            toleranceBefore: .zero,
            toleranceAfter: .zero
        ) { finished in
            Task { @MainActor in
                completion(finished)
            }
        }
    }
}

@MainActor
final class VideoLoopPlaybackCoordinator {
    private var generation = 0

    func invalidate() {
        generation += 1
    }

    func restartAfterPlaybackEnd(
        player: any VideoLoopPlaybackControlling,
        canRestart: @escaping @MainActor () -> Bool
    ) {
        let requestGeneration = generation
        guard canRestart() else { return }

        player.seekToStart { [weak self, weak player] finished in
            guard
                let self,
                let player,
                finished,
                requestGeneration == self.generation,
                canRestart()
            else {
                return
            }
            player.play()
        }
    }
}

@MainActor
@Observable
final class PlayerController {
    private(set) var player: AVPlayer?
    private(set) var shouldAutoplay = false
    private(set) var isActive = true
    // This mirrors AppModel's viewer-wide preference. It is deliberately not
    // reset when the current item is released or replaced.
    private(set) var isLooping = VideoPlaybackDefaults.looping
    private(set) var presentation: VideoPlaybackPresentation = .embedded

    @ObservationIgnored private var playbackEndObserver: NSObjectProtocol?
    @ObservationIgnored private let loopPlayback = VideoLoopPlaybackCoordinator()

    func load(
        fileURL: URL,
        autoplay: Bool,
        presentation: VideoPlaybackPresentation
    ) {
        player?.pause()
        removePlaybackEndObserver()
        loopPlayback.invalidate()
        shouldAutoplay = autoplay
        self.presentation = presentation
        replaceCurrentItem(fileURL: fileURL)
    }

    func setLooping(_ enabled: Bool) {
        isLooping = enabled
    }

    func toggleLooping() {
        setLooping(!isLooping)
    }

    func pause() {
        isActive = false
        player?.pause()
    }

    func resumeIfAppropriate() {
        isActive = true
        // PlayerViewControllerRepresentable resumes only after its requested
        // AVKit experience is ready. Playing here could bypass a pending
        // embedded-to-expanded transition for the active video.
    }

    func stop() {
        player?.pause()
        removePlaybackEndObserver()
        loopPlayback.invalidate()
        player?.replaceCurrentItem(with: nil)
        player = nil
        shouldAutoplay = false
        presentation = .embedded
    }

    private func replaceCurrentItem(fileURL: URL) {
        let item = AVPlayerItem(url: fileURL)
        let player: AVPlayer
        if let currentPlayer = self.player {
            currentPlayer.replaceCurrentItem(with: item)
            player = currentPlayer
        } else {
            player = AVPlayer(playerItem: item)
            self.player = player
        }
        player.automaticallyWaitsToMinimizeStalling = true

        playbackEndObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self, weak player] _ in
            Task { @MainActor in
                guard let self, let player else { return }
                self.handlePlaybackEnded(player)
            }
        }
    }

    private func handlePlaybackEnded(_ endedPlayer: AVPlayer) {
        loopPlayback.restartAfterPlaybackEnd(player: endedPlayer) { [weak self] in
            guard let self else { return false }
            return self.player === endedPlayer
                && self.isLooping
                && self.shouldAutoplay
                && self.isActive
        }
    }

    private func removePlaybackEndObserver() {
        guard let playbackEndObserver else { return }
        NotificationCenter.default.removeObserver(playbackEndObserver)
        self.playbackEndObserver = nil
    }
}
