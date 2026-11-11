import Foundation

protocol ClassifierServicing: Sendable {
    func status(mediaID: String) async throws -> ClassifierStatusResponse
    func classify(mediaIDs: [String], force: Bool) async throws -> ClassifierBatchResponse
    func setHumanRating(mediaID: String, rating: ClassifierRating) async throws -> ClassifierReview
    func clearHumanRating(mediaID: String) async throws
    func reviewQueue(scope: GalleryScope, limit: Int) async throws -> ClassifierQueueSnapshot
}

struct LiveClassifierService: ClassifierServicing {
    let apiClient: APIClient

    func status(mediaID: String) async throws -> ClassifierStatusResponse {
        try await apiClient.request(.classifierStatus(id: mediaID))
    }

    func classify(mediaIDs: [String], force: Bool = false) async throws -> ClassifierBatchResponse {
        try await apiClient.request(.startClassification(ids: mediaIDs, force: force))
    }

    func setHumanRating(mediaID: String, rating: ClassifierRating) async throws -> ClassifierReview {
        try await apiClient.request(.setClassifierReview(id: mediaID, rating: rating))
    }

    func clearHumanRating(mediaID: String) async throws {
        _ = try await apiClient.requestData(.clearClassifierReview(id: mediaID))
    }

    func reviewQueue(scope: GalleryScope, limit: Int) async throws -> ClassifierQueueSnapshot {
        var queueScope = scope
        queueScope.kind = .image
        queueScope.classifierStatus = .needsReview
        return try await apiClient.request(.classifierReviewQueueSnapshot(scope: queueScope, limit: limit))
    }
}
