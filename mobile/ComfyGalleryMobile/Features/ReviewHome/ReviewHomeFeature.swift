import SwiftUI
import OSLog

@MainActor
@Observable
final class ReviewHomeFeature {
    var summary: ReviewSummary?
    var sessions: [ReviewSession] = []
    var isLoading = false
    var errorMessage: String?
    var isCreating = false

    var sourceKind: SourceKind = .random
    var filterKind: MediaKind?
    var filterEvaluationState: EvaluationState?
    var randomLimit: Int = 100
    var orderingMode: OrderingMode = .random
    var includeCharacter: Bool = false

    private let apiClient: APIClient
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "ReviewHome")

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            async let summary: ReviewSummary = apiClient.request(.reviewSummary)
            async let sessions: [ReviewSession] = apiClient.request(.reviewSessions(limit: 25))
            self.summary = try await summary
            self.sessions = try await sessions
        } catch let error as APIError {
            errorMessage = error.errorDescription ?? "Could not load review data."
        } catch {
            errorMessage = "Could not load review data."
        }
        isLoading = false
    }

    func configureForQuickAction(_ kind: SourceKind) {
        sourceKind = kind
        switch kind {
        case .random:
            orderingMode = .random
        case .inProgress:
            orderingMode = .stable
        case .filter:
            orderingMode = .random
        }
    }

    func createSession() async -> ReviewSession? {
        isCreating = true
        errorMessage = nil
        let filter = filterForCurrentSource()
        let request = CreateSessionRequest(
            name: nil,
            sourceKind: sourceKind,
            filter: filter,
            randomLimit: randomLimit,
            orderingMode: orderingMode,
            optionalModules: includeCharacter ? ["character"] : []
        )
        logger.log("Creating session source=\(self.sourceKind.rawValue, privacy: .public) ordering=\(self.orderingMode.rawValue, privacy: .public)")
        do {
            let session: ReviewSession = try await apiClient.request(.createReviewSession(request))
            await load()
            isCreating = false
            return session
        } catch let error as APIError {
            errorMessage = error.errorDescription ?? "Could not create review session."
            isCreating = false
            return nil
        } catch {
            errorMessage = "Could not create review session."
            isCreating = false
            return nil
        }
    }

    func deleteSession(_ session: ReviewSession) async {
        do {
            let _: ReviewSession = try await apiClient.request(.deleteReviewSession(id: session.id))
            await load()
        } catch let error as APIError {
            errorMessage = error.errorDescription ?? "Could not delete session."
        } catch {
            errorMessage = "Could not delete session."
        }
    }

    private func filterForCurrentSource() -> MediaFilter? {
        switch sourceKind {
        case .random:
            return MediaFilter(kind: nil, evaluationState: .notStarted, trash: false)
        case .inProgress:
            return nil
        case .filter:
            return MediaFilter(
                kind: filterKind,
                evaluationState: filterEvaluationState ?? .notStarted,
                trash: false
            )
        }
    }
}
