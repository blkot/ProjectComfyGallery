import AVFoundation
import Foundation
import Observation

enum VideoPlaybackDefaults {
    static let autoplay = true
    static let looping = true
}

struct VideoPlaybackReadiness: Equatable {
    private(set) var itemGeneration = 0
    private(set) var isPlayerItemReadyToPlay = false
    private(set) var isVideoReadyToRender = false

    var isReady: Bool {
        isPlayerItemReadyToPlay && isVideoReadyToRender
    }

    mutating func reset(for itemGeneration: Int) {
        self.itemGeneration = itemGeneration
        isPlayerItemReadyToPlay = false
        isVideoReadyToRender = false
    }

    @discardableResult
    mutating func updatePlayerItem(
        isReady: Bool,
        itemGeneration: Int
    ) -> Bool {
        guard itemGeneration == self.itemGeneration else { return false }
        isPlayerItemReadyToPlay = isReady
        return true
    }

    @discardableResult
    mutating func updateVideoRendering(
        isReady: Bool,
        itemGeneration: Int
    ) -> Bool {
        guard itemGeneration == self.itemGeneration else { return false }
        isVideoReadyToRender = isReady
        return true
    }
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
    private(set) var isPlaying = false
    private(set) var itemGeneration = 0
    private(set) var playbackError: String?
    // This mirrors AppModel's viewer-wide preference. It is deliberately not
    // reset when the current item is released or replaced.
    private(set) var isLooping = VideoPlaybackDefaults.looping
    private(set) var presentation: VideoPlaybackPresentation = .embedded

    @ObservationIgnored private var playbackEndObserver: NSObjectProtocol?
    @ObservationIgnored private var playbackFailureObserver: NSObjectProtocol?
    @ObservationIgnored private var playerItemStatusObservation: NSKeyValueObservation?
    @ObservationIgnored private let loopPlayback = VideoLoopPlaybackCoordinator()
    @ObservationIgnored private var isPausedByUser = false
    @ObservationIgnored private var readiness = VideoPlaybackReadiness()

    var isReadyForPlayback: Bool {
        readiness.isReady
    }

    func load(
        fileURL: URL,
        autoplay: Bool,
        presentation: VideoPlaybackPresentation
    ) {
        player?.pause()
        isPlaying = false
        removePlaybackObservers()
        loopPlayback.invalidate()
        shouldAutoplay = autoplay
        self.presentation = presentation
        isPausedByUser = false
        playbackError = nil
        itemGeneration += 1
        readiness.reset(for: itemGeneration)
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
        isPlaying = false
    }

    func resumeIfAppropriate() {
        isActive = true
        startPlaybackIfAppropriate()
    }

    func startPlaybackIfAppropriate() {
        guard
            shouldAutoplay,
            isActive,
            !isPausedByUser,
            !isPlaying,
            readiness.isReady,
            playbackError == nil,
            let player
        else {
            return
        }
        player.play()
        isPlaying = true
    }

    func togglePlayback() {
        guard let player else { return }
        if isPlaying {
            player.pause()
            isPlaying = false
            isPausedByUser = true
        } else {
            playbackError = nil
            isPausedByUser = false
            startPlaybackIfAppropriate()
        }
    }

    func updatePlayerItemReadiness(
        isReady: Bool,
        itemGeneration: Int
    ) {
        guard readiness.updatePlayerItem(
            isReady: isReady,
            itemGeneration: itemGeneration
        ) else {
            return
        }
        startPlaybackIfAppropriate()
    }

    func updateVideoRenderingReadiness(
        isReady: Bool,
        itemGeneration: Int
    ) {
        guard readiness.updateVideoRendering(
            isReady: isReady,
            itemGeneration: itemGeneration
        ) else {
            return
        }
        startPlaybackIfAppropriate()
    }

    func stop() {
        player?.pause()
        removePlaybackObservers()
        loopPlayback.invalidate()
        player?.replaceCurrentItem(with: nil)
        player = nil
        shouldAutoplay = false
        isPlaying = false
        isPausedByUser = false
        playbackError = nil
        itemGeneration += 1
        readiness.reset(for: itemGeneration)
        presentation = .embedded
    }

    private func replaceCurrentItem(fileURL: URL) {
        let item = AVPlayerItem(url: fileURL)
        let itemGeneration = itemGeneration
        let player: AVPlayer
        if let currentPlayer = self.player {
            currentPlayer.replaceCurrentItem(with: item)
            player = currentPlayer
        } else {
            player = AVPlayer(playerItem: item)
            self.player = player
        }
        player.automaticallyWaitsToMinimizeStalling = true
        observeStatus(of: item, itemGeneration: itemGeneration)

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

        playbackFailureObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemFailedToPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self, weak item] notification in
            let message = (
                notification.userInfo?[AVPlayerItemFailedToPlayToEndTimeErrorKey]
                    as? Error
            )?.localizedDescription ?? "This video could not be played."
            Task { @MainActor in
                guard
                    let self,
                    let item,
                    self.player?.currentItem === item,
                    self.itemGeneration == itemGeneration
                else {
                    return
                }
                self.playbackError = message
                self.isPlaying = false
            }
        }
    }

    private func handlePlaybackEnded(_ endedPlayer: AVPlayer) {
        guard
            player === endedPlayer,
            isLooping,
            shouldAutoplay,
            isActive,
            !isPausedByUser,
            readiness.isReady
        else {
            isPlaying = false
            return
        }
        loopPlayback.restartAfterPlaybackEnd(player: endedPlayer) { [weak self] in
            guard let self else { return false }
            return self.player === endedPlayer
                && self.isLooping
                && self.shouldAutoplay
                && self.isActive
                && !self.isPausedByUser
                && self.readiness.isReady
        }
    }

    private func observeStatus(
        of item: AVPlayerItem,
        itemGeneration: Int
    ) {
        playerItemStatusObservation = item.observe(
            \.status,
            options: [.initial, .new]
        ) { [weak self, weak item] observedItem, _ in
            Task { @MainActor in
                guard
                    let self,
                    let item,
                    item === observedItem,
                    self.player?.currentItem === item,
                    self.itemGeneration == itemGeneration
                else {
                    return
                }

                switch observedItem.status {
                case .readyToPlay:
                    self.updatePlayerItemReadiness(
                        isReady: true,
                        itemGeneration: itemGeneration
                    )
                case .failed:
                    self.updatePlayerItemReadiness(
                        isReady: false,
                        itemGeneration: itemGeneration
                    )
                    self.playbackError = observedItem.error?.localizedDescription
                        ?? "This video could not be played."
                    self.isPlaying = false
                case .unknown:
                    self.updatePlayerItemReadiness(
                        isReady: false,
                        itemGeneration: itemGeneration
                    )
                @unknown default:
                    self.updatePlayerItemReadiness(
                        isReady: false,
                        itemGeneration: itemGeneration
                    )
                }
            }
        }
    }

    private func removePlaybackObservers() {
        playerItemStatusObservation?.invalidate()
        playerItemStatusObservation = nil
        if let playbackEndObserver {
            NotificationCenter.default.removeObserver(playbackEndObserver)
            self.playbackEndObserver = nil
        }
        if let playbackFailureObserver {
            NotificationCenter.default.removeObserver(playbackFailureObserver)
            self.playbackFailureObserver = nil
        }
    }
}
