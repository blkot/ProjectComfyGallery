import SwiftUI
import OSLog

@MainActor
@Observable
final class ReviewWorkspaceFeature {
    let sessionID: String
    private(set) var reviewItem: ReviewItem?
    private(set) var position: Int = 0
    private(set) var isLoading = true
    private(set) var errorMessage: String?
    private(set) var saveState: SaveState = .saved

    private(set) var mediaImage: UIImage?
    private(set) var mediaVideoURL: URL?
    private(set) var mediaPosterImage: UIImage?
    private(set) var isLoadingMedia = false
    private(set) var loadMediaFailed = false

    var showConflict = false
    var conflictMessage = ""
    var conflictServerValue = ""
    var conflictLocalValue = ""

    var lastSaveError: String?
    var requiresReconnect = false

    private var lastActionDescription: String?
    private var lastActionCriterionID: String?
    private var lastActionPreviousValue: Int?

    private let apiClient: APIClient
    private let mediaRepository: MediaRepository
    private let commandQueue: ReviewCommandQueue
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "ReviewWorkspace")

    // Tracks the highest version we've ever seen for each evaluation ID. Used to
    // assign expected_version to outgoing requests even when the captured
    // Evaluation struct is stale (closures capture by value).
    private var latestKnownVersions: [String: Int] = [:]
    // Tracks in-flight commit tasks per criterion so a rapid second commit can
    // cancel the first.
    private var commitTasks: [String: Task<Void, Never>] = [:]

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

    // MARK: - Loading

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            try await fetchCurrentItem()
            seedLatestKnownVersions()
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
        let evalSummary = item.evaluations.map { "\($0.evaluationKind)(id=\($0.id.prefix(8)),criteria=\($0.criteria.count))" }.joined(separator: ", ")
        logger.log("Fetched item position=\(item.position) evaluations=[\(evalSummary, privacy: .public)]")
    }

    private func seedLatestKnownVersions() {
        guard let item = reviewItem else { return }
        for evaluation in item.evaluations {
            latestKnownVersions[evaluation.id] = evaluation.version
        }
        logger.log("Seeded versions: \(self.latestKnownVersions)")
    }

    // MARK: - Navigation

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

    // MARK: - Public actions (called by View, IDs only — no captured structs)

    func setScore(_ value: Int, criterionID: String, evaluationID: String) async {
        let previousValue = serverScoreValue(forCriterion: criterionID, evaluationID: evaluationID)
        lastActionDescription = "Set \(criterionID) to \(value)"
        lastActionCriterionID = criterionID
        lastActionPreviousValue = previousValue
        await runMutation(kind: .score, criterionID: criterionID, intendedValue: value, evaluationID: evaluationID)
    }

    func setNA(criterionID: String, evaluationID: String) async {
        let previousValue = serverScoreValue(forCriterion: criterionID, evaluationID: evaluationID)
        lastActionDescription = "Marked \(criterionID) as N/A"
        lastActionCriterionID = criterionID
        lastActionPreviousValue = previousValue
        await runMutation(kind: .na, criterionID: criterionID, intendedValue: nil, evaluationID: evaluationID)
    }

    func clearScore(criterionID: String, evaluationID: String) async {
        let previousValue = serverScoreValue(forCriterion: criterionID, evaluationID: evaluationID)
        lastActionDescription = "Cleared \(criterionID)"
        lastActionCriterionID = criterionID
        lastActionPreviousValue = previousValue
        await runMutation(kind: .clear, criterionID: criterionID, intendedValue: nil, evaluationID: evaluationID)
    }

    func toggleTrash(evaluationID: String) async {
        guard let eval = reviewItem?.evaluations.first(where: { $0.id == evaluationID }) else { return }
        lastActionDescription = eval.isTrash ? "Restored from trash" : "Moved to trash"
        lastActionCriterionID = nil
        lastActionPreviousValue = nil
        await runMutation(kind: eval.isTrash ? .restore : .trash, criterionID: nil, intendedValue: nil, evaluationID: evaluationID)
    }

    func undoLastAction() async {
        guard let evaluation = currentEvaluation,
              lastActionDescription != nil,
              let criterionID = lastActionCriterionID,
              let previousValue = lastActionPreviousValue,
              let criterion = evaluation.criteria.first(where: { $0.id == criterionID }) else {
            return
        }
        let kind: CommandKind = .score
        let intendedValue: Int? = previousValue
        lastActionDescription = nil
        lastActionCriterionID = nil
        lastActionPreviousValue = nil
        await runMutation(kind: kind, criterionID: criterion.id, intendedValue: intendedValue, evaluationID: evaluation.id)
    }

    func resolveConflict(useServerValue: Bool) async {
        showConflict = false
        if useServerValue {
            await load()
            saveState = .saved
        } else {
            saveState = .needsAttention
        }
    }

    // MARK: - Mutation pipeline

    private func runMutation(
        kind: CommandKind,
        criterionID: String?,
        intendedValue: Int?,
        evaluationID: String
    ) async {
        guard let evaluation = reviewItem?.evaluations.first(where: { $0.id == evaluationID }) else {
            saveState = .needsAttention
            lastSaveError = "This evaluation is no longer available."
            return
        }

        // Always use the highest known version, even if the captured Evaluation
        // struct (or its container) is stale.
        let expectedVersion = latestKnownVersions[evaluation.id] ?? evaluation.version
        let profileID = (try? localStore.activeProfile()?.uuid) ?? ""
        let mutation = PendingMutation(
            serverProfileUUID: profileID,
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            criterionVersionUUID: criterionID,
            commandKind: kind,
            intendedValue: intendedValue,
            baseEvaluationVersion: expectedVersion
        )

        logger.log("runMutation kind=\(kind.rawValue, privacy: .public) criterion=\(criterionID ?? "—", privacy: .public) eval=\(evaluation.id, privacy: .public) expectedVersion=\(expectedVersion)")

        saveState = .saving

        do {
            try localStore.insertPendingMutation(mutation)
        } catch {
            logger.error("Failed to insert pending mutation: \(error.localizedDescription)")
            saveState = .needsAttention
            return
        }

        do {
            let updated = try await commandQueue.enqueue(mutation)
            latestKnownVersions[updated.id] = updated.version
            applyEvaluationUpdate(updated)
            try? localStore.deletePendingMutation(mutation)
            saveState = .saved
            lastSaveError = nil
            logger.log("Mutation succeeded, new version=\(updated.version)")
        } catch let error as APIError {
            switch error {
            case .conflict(let envelope):
                logger.error("Conflict on \(evaluation.id, privacy: .public): \(envelope.error.message, privacy: .public)")
                presentConflict(envelope: envelope, localDescription: mutation.commandKind.rawValue)
                try? localStore.deletePendingMutation(mutation)
                saveState = .needsAttention
                lastSaveError = envelope.error.message
                await load()
            case .unauthorized, .forbidden:
                logger.error("Auth error on \(evaluation.id, privacy: .public): \(error.localizedDescription, privacy: .public)")
                saveState = .needsAttention
                lastSaveError = "Your session is no longer valid. Please reconnect."
                try? localStore.deletePendingMutation(mutation)
                requiresReconnect = true
            default:
                if error.isRetryable {
                    saveState = .savedLocally
                    lastSaveError = error.errorDescription
                } else {
                    try? localStore.deletePendingMutation(mutation)
                    saveState = .needsAttention
                    lastSaveError = error.errorDescription
                    errorMessage = error.errorDescription
                }
            }
        } catch {
            logger.error("Unknown error: \(error.localizedDescription)")
            saveState = .savedLocally
            lastSaveError = error.localizedDescription
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
        let previousState: ProgressState? = evaluations.first(where: { $0.id == updated.id })?.progressState
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
        if previousState != updated.progressState {
            logger.log("Evaluation \(updated.id, privacy: .public) state: \(String(describing: previousState)) -> \(String(describing: updated.progressState))")
        }
    }

    var primaryEvaluationState: ProgressState? {
        currentEvaluation?.progressState
    }

    func criteriaCompletion(forEvaluation evalID: String) -> (scored: Int, total: Int) {
        guard let eval = reviewItem?.evaluations.first(where: { $0.id == evalID }) else {
            return (0, 0)
        }
        let total = eval.criteria.count
        let scored = eval.criteria.filter { c in
            eval.scores.contains { $0.criterionVersionId == c.id && ($0.state == .scored || $0.state == .na) }
        }.count
        return (scored, total)
    }

    // MARK: - Reads

    var currentEvaluation: Evaluation? { reviewItem?.evaluations.first }

    func evaluation(id: String) -> Evaluation? {
        reviewItem?.evaluations.first { $0.id == id }
    }

    func score(forCriterion criterionID: String, evaluationID: String) -> EvaluationScore? {
        guard let eval = evaluation(id: evaluationID) else { return nil }
        return eval.scores.first { $0.criterionVersionId == criterionID }
    }

    private func serverScoreValue(forCriterion criterionID: String, evaluationID: String) -> Int? {
        guard let score = score(forCriterion: criterionID, evaluationID: evaluationID), score.state == .scored else { return nil }
        return score.value
    }

    var isLastItem: Bool {
        guard let item = reviewItem else { return false }
        return item.position >= item.session.candidateCount - 1
    }

    // MARK: - Media

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
}
