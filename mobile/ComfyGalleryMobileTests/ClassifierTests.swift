import XCTest
@testable import ComfyGalleryMobile

@MainActor
final class ClassifierTests: XCTestCase {
    func testEffectiveRatingAndStatusRespectHumanPrecedence() {
        let assessment = MediaSafetyAssessmentSummary(status: "completed", label: "Normal", suggestedRating: .safe, confidence: 0.99, needsReview: false)
        let review = MediaSafetyReviewSummary(rating: .nudity, reviewedAt: "2026-11-11T01:00:00Z")

        XCTAssertEqual(ClassifierProjection.effectiveRating(assessment: assessment, review: review), .nudity)
        XCTAssertEqual(ClassifierProjection.status(assessment: assessment, review: review), .reviewed)
        XCTAssertEqual(ClassifierProjection.effectiveRating(assessment: assessment, review: nil), .safe)
        XCTAssertEqual(ClassifierProjection.status(assessment: nil, review: nil), .unclassified)
        XCTAssertEqual(ClassifierProjection.status(
            assessment: MediaSafetyAssessmentSummary(status: "completed", label: nil, suggestedRating: .review, confidence: 0.4, needsReview: true),
            review: nil
        ), .needsReview)
    }

    func testClassifierQueueStorePersistsAndClearsProtectedSnapshot() throws {
        let directory = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString, directoryHint: .isDirectory)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = ClassifierReviewQueueStore(directoryURL: directory)
        let queue = ClassifierReviewQueue(
            snapshot: ClassifierQueueSnapshot(ids: ["a", "b", "c"], total: 210, truncated: true),
            position: 1
        )

        try store.save(queue)
        let restored = try XCTUnwrap(store.load())
        XCTAssertEqual(restored.id, queue.id)
        XCTAssertEqual(restored.mediaIDs, ["a", "b", "c"])
        XCTAssertEqual(restored.currentID, "b")
        XCTAssertTrue(restored.truncated)

        try store.save(nil)
        XCTAssertNil(try store.load())
    }

    func testDisabledClassifierHasActionableServerError() {
        let envelope = APIErrorEnvelope(error: .init(
            code: "NSFW_CLASSIFIER_DISABLED",
            message: "Classifier disabled.",
            details: nil,
            requestId: nil
        ))

        XCTAssertEqual(APIError.map(statusCode: 503, envelope: envelope), .classifierUnavailable)
        XCTAssertFalse(APIError.classifierUnavailable.isRetryable)
    }
}
