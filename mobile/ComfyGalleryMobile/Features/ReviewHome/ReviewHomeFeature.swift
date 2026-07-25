import SwiftUI
import OSLog

@MainActor
@Observable
final class ReviewHomeFeature {
    var summary: ReviewSummary?
    var sessions: [ReviewSession] = []
    var isLoading = false
    var errorMessage: String?

    var sourceKind: SourceKind = .random
    var filterKind: MediaKind?
    var filterEvaluationState: EvaluationState?
    var randomLimit: Int = 100
    var orderingMode: OrderingMode = .random
    var includeCharacter: Bool = false

    private let apiClient: APIClient

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
        } catch {
            errorMessage = "Could not load review data."
        }
        isLoading = false
    }

    func createSession() async -> ReviewSession? {
        let filter: MediaFilter? = sourceKind == .filter
            ? MediaFilter(kind: filterKind, evaluationState: filterEvaluationState, trash: false)
            : nil
        let request = CreateSessionRequest(
            name: nil,
            sourceKind: sourceKind,
            filter: filter,
            randomLimit: randomLimit,
            orderingMode: orderingMode,
            optionalModules: includeCharacter ? ["character"] : []
        )
        do {
            let session: ReviewSession = try await apiClient.request(.createReviewSession(request))
            await load()
            return session
        } catch {
            errorMessage = "Could not create review session."
            return nil
        }
    }

    func deleteSession(_ session: ReviewSession) async {
        do {
            let _: ReviewSession = try await apiClient.request(.deleteReviewSession(id: session.id))
            await load()
        } catch {
            errorMessage = "Could not delete session."
        }
    }
}
