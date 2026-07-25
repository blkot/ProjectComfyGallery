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

    var showConflict = false
    var conflictMessage = ""
    var conflictServerValue = ""
    var conflictLocalValue = ""

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
        do { try await fetchCurrentItem() }
        catch { errorMessage = "Could not load review item." }
        isLoading = false
    }

    private func fetchCurrentItem() async throws {
        let item: ReviewItem = try await apiClient.request(.reviewItem(sessionID: sessionID, position: position))
        reviewItem = item
        position = item.position
    }

    func navigateToPrevious() async {
        guard position > 0, saveState != .saving else { return }
        do {
            try await updateCursor(position - 1)
            position -= 1
            await load()
        } catch { errorMessage = "Could not navigate." }
    }

    func navigateToNext() async {
        guard let item = reviewItem, position < item.session.candidateCount - 1, saveState != .saving else { return }
        do {
            try await updateCursor(position + 1)
            position += 1
            await load()
        } catch { errorMessage = "Could not navigate." }
    }

    func stop() async {}

    private func updateCursor(_ cursor: Int) async throws {
        let body = PatchSessionBody(currentCursor: cursor, status: nil)
        let _: ReviewSession = try await apiClient.request(.patchReviewSession(id: sessionID, body))
    }

    func setScore(_ value: Int, for criterion: Criterion, evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "",
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion.id,
            commandKind: .score,
            intendedValue: value,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch let error as APIError {
            saveState = error.isRetryable ? .savedLocally : .needsAttention
        } catch {
            saveState = .savedLocally
        }
    }

    func setNA(for criterion: Criterion, evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "", reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "", evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion.id, commandKind: .na,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch { saveState = .savedLocally }
    }

    func clearScore(for criterion: Criterion, evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "", reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "", evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion.id, commandKind: .clear,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch { saveState = .savedLocally }
    }

    func toggleTrash(evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "", reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "", evaluationUUID: evaluation.id,
            commandKind: evaluation.isTrash ? .restore : .trash,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch { saveState = .savedLocally }
    }

    func undoLastAction() async {
        try? await fetchCurrentItem()
        saveState = .saved
    }

    func resolveConflict(useServerValue: Bool) async {
        showConflict = false
        if useServerValue {
            try? await fetchCurrentItem()
            saveState = .saved
        }
    }

    func finishSession() async {
        let body = PatchSessionBody(currentCursor: nil, status: .finished)
        do {
            let _: ReviewSession = try await apiClient.request(.patchReviewSession(id: sessionID, body))
        } catch { errorMessage = "Could not finish session." }
    }

    var currentEvaluation: Evaluation? { reviewItem?.evaluations.first }

    var scoreForCriterion: (Criterion) -> EvaluationScore? {
        { criterion in self.currentEvaluation?.scores.first { $0.criterionVersionId == criterion.id } }
    }

    var isLastItem: Bool {
        guard let item = reviewItem else { return false }
        return item.position >= item.session.candidateCount - 1
    }
}
