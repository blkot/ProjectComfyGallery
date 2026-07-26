import SwiftUI
import OSLog

@MainActor
@Observable
final class ReviewWorkspaceFeature {
    let sessionID: String
    var reviewItem: ReviewItem?
    var position: Int = 0
    var isLoading = true
    var errorMessage: String?
    var saveState: SaveState = .saved

    var mediaImage: UIImage?
    var mediaVideoURL: URL?
    var mediaPosterImage: UIImage?
    var isLoadingMedia = false
    var loadMediaFailed = false

    var showConflict = false
    var conflictMessage = ""
    var conflictServerValue = ""
    var conflictLocalValue = ""

    private var lastActionDescription: String?
    private var lastActionCriterionID: String?
    private var lastActionPreviousValue: Int?

    private let apiClient: APIClient
    private let mediaRepository: MediaRepository
    private let commandQueue: ReviewCommandQueue
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "ReviewWorkspace")

    enum SaveState {
        case saved, saving, savedLocally, needsAttention
    }

    init(
        sessionID: String,
        apiClient: APIClient,
        mediaRepository: MediaRepository,
        commandQueue: ReviewCommandQueue,
        localStore: LocalStore
    ) {
        self.sessionID = sessionID
        self.apiClient = apiClient
        self.mediaRepository = mediaRepository
        self.commandQueue = commandQueue
        self.localStore = localStore
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            try await fetchCurrentItem()
            await loadMedia()
        } catch let error as APIError {
            errorMessage = error.errorDescription ?? "Could not load review item."
        } catch {
            errorMessage = "Could not load review item."
        }
        isLoading = false
    }

    private func fetchCurrentItem() async throws {
        let item: ReviewItem = try await apiClient.request(.reviewItem(sessionID: sessionID, position: position))
        reviewItem = item
        position = item.position
    }

    func navigateToPrevious() async {
        guard position > 0, saveState != .saving else { return }
        await goTo(position - 1)
    }

    func navigateToNext() async {
        guard let item = reviewItem, position < item.session.candidateCount - 1, saveState != .saving else { return }
        await goTo(position + 1)
    }

    private func goTo(_ newPosition: Int) async {
        do {
            try await updateCursor(newPosition)
            position = newPosition
            await load()
        } catch let error as APIError {
            errorMessage = error.errorDescription ?? "Could not navigate."
        } catch {
            errorMessage = "Could not navigate."
        }
    }

    func stop() async {
        try? await updateCursor(position)
    }

    private func updateCursor(_ cursor: Int) async throws {
        let body = PatchSessionBody(currentCursor: cursor, status: nil)
        let _: ReviewSession = try await apiClient.request(.patchReviewSession(id: sessionID, body))
    }

    func setScore(_ value: Int, for criterion: Criterion, evaluation: Evaluation) async {
        let previousValue = currentScoreValue(for: criterion, in: evaluation)
        lastActionDescription = "Set \(criterion.label) to \(value)"
        lastActionCriterionID = criterion.id
        lastActionPreviousValue = previousValue

        await runMutation(
            kind: .score,
            evaluation: evaluation,
            criterion: criterion,
            intendedValue: value,
            expectedVersion: evaluation.version
        )
    }

    func setNA(for criterion: Criterion, evaluation: Evaluation) async {
        let previousValue = currentScoreValue(for: criterion, in: evaluation)
        lastActionDescription = "Marked \(criterion.label) as N/A"
        lastActionCriterionID = criterion.id
        lastActionPreviousValue = previousValue

        await runMutation(
            kind: .na,
            evaluation: evaluation,
            criterion: criterion,
            intendedValue: nil,
            expectedVersion: evaluation.version
        )
    }

    func clearScore(for criterion: Criterion, evaluation: Evaluation) async {
        let previousValue = currentScoreValue(for: criterion, in: evaluation)
        lastActionDescription = "Cleared \(criterion.label)"
        lastActionCriterionID = criterion.id
        lastActionPreviousValue = previousValue

        await runMutation(
            kind: .clear,
            evaluation: evaluation,
            criterion: criterion,
            intendedValue: nil,
            expectedVersion: evaluation.version
        )
    }

    func toggleTrash(evaluation: Evaluation) async {
        lastActionDescription = evaluation.isTrash ? "Restored from trash" : "Moved to trash"
        lastActionCriterionID = nil
        lastActionPreviousValue = nil

        await runMutation(
            kind: evaluation.isTrash ? .restore : .trash,
            evaluation: evaluation,
            criterion: nil,
            intendedValue: nil,
            expectedVersion: evaluation.version
        )
    }

    func undoLastAction() async {
        guard let evaluation = currentEvaluation,
              let _ = lastActionDescription,
              let criterionID = lastActionCriterionID,
              let previousValue = lastActionPreviousValue,
              let criterion = evaluation.criteria.first(where: { $0.id == criterionID }) else {
            return
        }
        let kind: CommandKind
        var intendedValue: Int? = nil
        kind = .score
        intendedValue = previousValue
        lastActionDescription = nil
        lastActionCriterionID = nil
        lastActionPreviousValue = nil

        await runMutation(
            kind: kind,
            evaluation: evaluation,
            criterion: criterion,
            intendedValue: intendedValue,
            expectedVersion: evaluation.version
        )
    }

    func resolveConflict(useServerValue: Bool) async {
        showConflict = false
        if useServerValue {
            try? await fetchCurrentItem()
            saveState = .saved
        } else {
            saveState = .needsAttention
        }
    }

    func finishSession() async {
        let body = PatchSessionBody(currentCursor: nil, status: .finished)
        do {
            let _: ReviewSession = try await apiClient.request(.patchReviewSession(id: sessionID, body))
        } catch let error as APIError {
            errorMessage = error.errorDescription ?? "Could not finish session."
        } catch {
            errorMessage = "Could not finish session."
        }
    }

    private func runMutation(
        kind: CommandKind,
        evaluation: Evaluation,
        criterion: Criterion?,
        intendedValue: Int?,
        expectedVersion: Int
    ) async {
        saveState = .saving
        let profileID = (try? localStore.activeProfile()?.uuid) ?? ""
        let mutation = PendingMutation(
            serverProfileUUID: profileID,
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion?.id,
            commandKind: kind,
            intendedValue: intendedValue,
            baseEvaluationVersion: expectedVersion
        )

        do {
            try localStore.insertPendingMutation(mutation)
        } catch {
            logger.error("Failed to insert pending mutation: \(error.localizedDescription)")
            saveState = .needsAttention
            return
        }

        do {
            let updatedEvaluation = try await commandQueue.enqueue(mutation)
            applyEvaluationUpdate(updatedEvaluation)
            try? localStore.deletePendingMutation(mutation)
            saveState = .saved
        } catch let error as APIError {
            switch error {
            case .conflict(let envelope):
                presentConflict(envelope: envelope, localDescription: mutation.commandKind.rawValue)
                try? localStore.deletePendingMutation(mutation)
                saveState = .needsAttention
            case .unauthorized, .forbidden:
                saveState = .needsAttention
            default:
                if error.isRetryable {
                    saveState = .savedLocally
                } else {
                    try? localStore.deletePendingMutation(mutation)
                    saveState = .needsAttention
                    errorMessage = error.errorDescription
                }
            }
        } catch {
            saveState = .savedLocally
        }
    }

    private func presentConflict(envelope: APIErrorEnvelope, localDescription: String) {
        conflictMessage = envelope.error.message
        conflictServerValue = envelope.error.code
        conflictLocalValue = localDescription
        showConflict = true
    }

    private func applyEvaluationUpdate(_ updated: Evaluation) {
        guard let item = reviewItem else { return }
        var evaluations = item.evaluations
        if let index = evaluations.firstIndex(where: { $0.id == updated.id }) {
            evaluations[index] = updated
        } else {
            evaluations.append(updated)
        }
        reviewItem = ReviewItem(
            session: item.session,
            position: item.position,
            media: item.media,
            prompts: item.prompts,
            evaluations: evaluations
        )
    }

    private func currentScoreValue(for criterion: Criterion, in evaluation: Evaluation) -> Int? {
        if let score = evaluation.scores.first(where: { $0.criterionVersionId == criterion.id }),
           score.state == .scored {
            return score.value
        }
        return nil
    }

    private func loadMedia() async {
        guard let item = reviewItem else { return }
        mediaImage = nil
        mediaVideoURL = nil
        mediaPosterImage = nil
        loadMediaFailed = false
        isLoadingMedia = true

        let targetSize = CGSize(width: UIScreen.main.bounds.width, height: UIScreen.main.bounds.height)
        do {
            let poster = try await mediaRepository.fetchPreviewImage(
                mediaID: item.media.id,
                targetSize: targetSize
            )
            mediaPosterImage = poster
            if item.media.kind == .image {
                mediaImage = poster
            } else if item.media.kind == .video {
                mediaVideoURL = try await mediaRepository.fetchPlaybackVideo(mediaID: item.media.id)
            }
        } catch {
            loadMediaFailed = true
        }
        isLoadingMedia = false
    }

    func reloadMedia() async {
        await loadMedia()
    }

    var currentEvaluation: Evaluation? { reviewItem?.evaluations.first }

    func score(for criterion: Criterion) -> EvaluationScore? {
        currentEvaluation?.scores.first { $0.criterionVersionId == criterion.id }
    }

    var isLastItem: Bool {
        guard let item = reviewItem else { return false }
        return item.position >= item.session.candidateCount - 1
    }
}
