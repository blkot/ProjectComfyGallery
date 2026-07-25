import XCTest
@testable import ComfyGalleryMobile

final class ReviewCommandQueueTests: XCTestCase {
    func testPendingMutationCreation() {
        let mutation = PendingMutation(
            serverProfileUUID: "p", reviewSessionUUID: "s", mediaUUID: "m",
            evaluationUUID: "e", criterionVersionUUID: "c", commandKind: .score,
            intendedValue: 7, baseEvaluationVersion: 3
        )
        XCTAssertEqual(mutation.commandKind, .score)
        XCTAssertEqual(mutation.intendedValue, 7)
        XCTAssertEqual(mutation.baseEvaluationVersion, 3)
        XCTAssertEqual(mutation.attemptCount, 0)
    }

    func testCommandKinds() {
        let score = PendingMutation(serverProfileUUID: "p", reviewSessionUUID: "s", mediaUUID: "m", evaluationUUID: "e", commandKind: .score, baseEvaluationVersion: 1)
        XCTAssertEqual(score.commandKind, .score)
        let trash = PendingMutation(serverProfileUUID: "p", reviewSessionUUID: "s", mediaUUID: "m", evaluationUUID: "e", commandKind: .trash, baseEvaluationVersion: 1)
        XCTAssertEqual(trash.commandKind, .trash)
    }

    func testAllCommandKinds() {
        let kinds: [CommandKind] = [.score, .na, .clear, .trash, .restore]
        for kind in kinds {
            let m = PendingMutation(serverProfileUUID: "p", reviewSessionUUID: "s", mediaUUID: "m", evaluationUUID: "e", commandKind: kind, baseEvaluationVersion: 1)
            XCTAssertEqual(m.commandKind, kind)
        }
    }
}
