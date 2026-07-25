import XCTest
@testable import ComfyGalleryMobile

final class EnumDecodingTests: XCTestCase {
    func testDecodeMediaPage() throws {
        let json = """
        {"items":[{"id":"019f-test","kind":"image","evaluation_state":"in_progress","is_trash":false,"preview_url":"/api/v1/media/019f-test/preview","filename":"ignored.jpg"}],"total":1,"limit":48,"offset":0}
        """.data(using: .utf8)!
        let page = try JSONDecoder().decode(MediaPage.self, from: json)
        XCTAssertEqual(page.items.count, 1)
        XCTAssertEqual(page.items[0].kind, .image)
        XCTAssertEqual(page.items[0].evaluationState, .inProgress)
    }

    func testDecodeReviewItem() throws {
        let json = """
        {"session":{"id":"s1","current_cursor":5,"candidate_count":100},"position":5,"media":{"id":"m1","kind":"image","preview_url":"/p","playback_url":null,"width":1024,"height":1536,"duration_seconds":null},"prompts":[{"role":"positive","label":"Prompt","text":"A landscape"}],"evaluations":[{"id":"e1","evaluation_kind":"base","progress_state":"in_progress","is_trash":false,"version":3,"criteria":[{"id":"c1","label":"Aesthetic","description":null,"min_value":0,"max_value":10}],"scores":[]}]}
        """.data(using: .utf8)!
        let item = try JSONDecoder().decode(ReviewItem.self, from: json)
        XCTAssertEqual(item.position, 5)
        XCTAssertEqual(item.media.kind, .image)
        XCTAssertEqual(item.prompts.count, 1)
        XCTAssertEqual(item.evaluations[0].criteria.count, 1)
    }

    func testScoreStateValues() {
        XCTAssertEqual(ScoreState.unset.rawValue, "unset")
        XCTAssertEqual(ScoreState.scored.rawValue, "scored")
        XCTAssertEqual(ScoreState.na.rawValue, "na")
    }
}
