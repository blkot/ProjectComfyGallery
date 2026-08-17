import Foundation
import Observation

enum MediaSequencePlaybackDefaults {
    static let imageDwellDuration: Duration = .seconds(5)
}

@MainActor
@Observable
final class MediaSequencePlaybackController {
    typealias Sleep = @Sendable (Duration) async throws -> Void

    private(set) var isEnabled = false

    @ObservationIgnored var onAdvance: (@MainActor (UUID) -> Bool)?
    @ObservationIgnored private let imageDwellDuration: Duration
    @ObservationIgnored private let sleep: Sleep
    @ObservationIgnored private var advanceTask: Task<Void, Never>?
    @ObservationIgnored private var currentMediaID: UUID?
    @ObservationIgnored private var currentKind: MediaKind?
    @ObservationIgnored private var isActive = true

    init(
        imageDwellDuration: Duration = MediaSequencePlaybackDefaults.imageDwellDuration,
        sleep: @escaping Sleep = { duration in
            try await Task.sleep(for: duration)
        }
    ) {
        self.imageDwellDuration = imageDwellDuration
        self.sleep = sleep
    }

    func start() {
        guard !isEnabled else { return }
        isEnabled = true
        scheduleImageAdvanceIfNeeded()
    }

    func stop() {
        isEnabled = false
        cancelPendingAdvance()
    }

    func reset() {
        stop()
        currentMediaID = nil
        currentKind = nil
    }

    func currentMediaWillChange() {
        cancelPendingAdvance()
        currentMediaID = nil
        currentKind = nil
    }

    func currentMediaDidBecomeReady(mediaID: UUID, kind: MediaKind) {
        cancelPendingAdvance()
        currentMediaID = mediaID
        currentKind = kind
        scheduleImageAdvanceIfNeeded()
    }

    func scenePhaseChanged(isActive: Bool) {
        self.isActive = isActive
        if isActive {
            scheduleImageAdvanceIfNeeded()
        } else {
            cancelPendingAdvance()
        }
    }

    /// Returns true when sequence playback consumed the video-end event. This
    /// suppresses single-video looping even when the filtered sequence reached
    /// its final item.
    @discardableResult
    func videoDidReachEnd(mediaID: UUID) -> Bool {
        guard
            isEnabled,
            isActive,
            currentMediaID == mediaID,
            currentKind == .video
        else {
            return false
        }
        attemptAdvance(from: mediaID)
        return true
    }

    private func scheduleImageAdvanceIfNeeded() {
        guard
            advanceTask == nil,
            isEnabled,
            isActive,
            currentKind == .image,
            let mediaID = currentMediaID
        else {
            return
        }

        advanceTask = Task { [weak self, sleep, imageDwellDuration] in
            do {
                try await sleep(imageDwellDuration)
                try Task.checkCancellation()
            } catch {
                return
            }
            guard let self else { return }
            self.advanceTask = nil
            guard
                self.isEnabled,
                self.isActive,
                self.currentMediaID == mediaID,
                self.currentKind == .image
            else {
                return
            }
            self.attemptAdvance(from: mediaID)
        }
    }

    private func attemptAdvance(from mediaID: UUID) {
        guard onAdvance?(mediaID) == true else {
            stop()
            return
        }
    }

    private func cancelPendingAdvance() {
        advanceTask?.cancel()
        advanceTask = nil
    }
}
