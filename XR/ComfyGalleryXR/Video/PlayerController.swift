import AVFoundation
import Foundation
import Observation

@MainActor
@Observable
final class PlayerController {
    private(set) var player: AVPlayer?
    private(set) var shouldAutoplay = false
    private(set) var isActive = true
    // This mirrors AppModel's viewer-wide preference. It is deliberately not
    // reset when the current item is released or replaced.
    private(set) var isLooping = false
    private(set) var presentation: VideoPlaybackPresentation = .embedded

    @ObservationIgnored private var playbackEndObserver: NSObjectProtocol?

    func load(
        fileURL: URL,
        autoplay: Bool,
        presentation: VideoPlaybackPresentation
    ) {
        player?.pause()
        removePlaybackEndObserver()
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
        // embedded-to-expanded transition for spatial video.
    }

    func stop() {
        player?.pause()
        removePlaybackEndObserver()
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
        guard
            player === endedPlayer,
            isLooping
        else {
            return
        }
        endedPlayer.seek(
            to: .zero,
            toleranceBefore: .zero,
            toleranceAfter: .zero
        )
        if shouldAutoplay, isActive {
            endedPlayer.play()
        }
    }

    private func removePlaybackEndObserver() {
        guard let playbackEndObserver else { return }
        NotificationCenter.default.removeObserver(playbackEndObserver)
        self.playbackEndObserver = nil
    }
}
