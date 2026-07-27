import AVFoundation
import Foundation
import Observation

@MainActor
@Observable
final class PlayerController {
    private(set) var player: AVPlayer?
    private(set) var shouldAutoplay = false
    private(set) var isActive = true
    private(set) var isLooping = false

    @ObservationIgnored private var currentFileURL: URL?
    @ObservationIgnored private var looper: AVPlayerLooper?

    func load(fileURL: URL, autoplay: Bool) {
        stop()
        currentFileURL = fileURL
        shouldAutoplay = autoplay
        configurePlayer(
            fileURL: fileURL,
            startTime: .zero,
            playWhenReady: autoplay && isActive
        )
    }

    func toggleLooping() {
        guard let currentFileURL else { return }

        let currentTime = player?.currentTime() ?? .zero
        let wasPlaying = player?.timeControlStatus == .playing
            || player?.timeControlStatus == .waitingToPlayAtSpecifiedRate

        isLooping.toggle()
        configurePlayer(
            fileURL: currentFileURL,
            startTime: currentTime,
            playWhenReady: wasPlaying && isActive
        )
    }

    func pause() {
        isActive = false
        player?.pause()
    }

    func resumeIfAppropriate() {
        isActive = true
        if shouldAutoplay {
            player?.play()
        }
    }

    func stop() {
        player?.pause()
        looper?.disableLooping()
        looper = nil
        if let queuePlayer = player as? AVQueuePlayer {
            queuePlayer.removeAllItems()
        } else {
            player?.replaceCurrentItem(with: nil)
        }
        player = nil
        currentFileURL = nil
        shouldAutoplay = false
        isLooping = false
    }

    private func configurePlayer(
        fileURL: URL,
        startTime: CMTime,
        playWhenReady: Bool
    ) {
        player?.pause()
        looper?.disableLooping()
        looper = nil

        let item = AVPlayerItem(url: fileURL)
        let queuePlayer = AVQueuePlayer()
        queuePlayer.automaticallyWaitsToMinimizeStalling = true

        if isLooping {
            looper = AVPlayerLooper(player: queuePlayer, templateItem: item)
        } else {
            queuePlayer.insert(item, after: nil)
        }

        player = queuePlayer

        if startTime.isValid,
           !startTime.isIndefinite,
           CMTimeCompare(startTime, .zero) > 0 {
            queuePlayer.seek(
                to: startTime,
                toleranceBefore: .zero,
                toleranceAfter: .zero
            )
        }

        if playWhenReady {
            queuePlayer.play()
        }
    }
}
