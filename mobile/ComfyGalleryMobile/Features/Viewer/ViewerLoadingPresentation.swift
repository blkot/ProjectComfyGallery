import Foundation
import Observation

@MainActor
@Observable
final class ViewerLoadingPresentation {
    private(set) var isVisible = false

    private var activeRequestID: UUID?
    private var revealTask: Task<Void, Never>?
    private let revealDelay: Duration

    init(revealDelay: Duration = .milliseconds(200)) {
        self.revealDelay = revealDelay
    }

    func begin() -> UUID {
        revealTask?.cancel()

        let requestID = UUID()
        activeRequestID = requestID
        isVisible = false
        revealTask = Task { [weak self] in
            guard let self else { return }
            do {
                try await Task.sleep(for: revealDelay)
            } catch {
                return
            }

            guard !Task.isCancelled, activeRequestID == requestID else { return }
            isVisible = true
        }
        return requestID
    }

    func finish(_ requestID: UUID) {
        guard activeRequestID == requestID else { return }
        activeRequestID = nil
        revealTask?.cancel()
        revealTask = nil
        isVisible = false
    }
}
