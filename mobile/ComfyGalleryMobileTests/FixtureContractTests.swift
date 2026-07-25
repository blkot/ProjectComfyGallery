import XCTest
@testable import ComfyGalleryMobile

final class FixtureContractTests: XCTestCase {
    func testDecodeError401Fixture() throws {
        let json = """
        {"error":{"code":"UNAUTHORIZED","message":"Invalid or expired token","details":{},"request_id":"req-error-401"}}
        """.data(using: .utf8)!
        let envelope = try JSONDecoder().decode(APIErrorEnvelope.self, from: json)
        XCTAssertEqual(envelope.error.code, "UNAUTHORIZED")
    }

    func testDecodeError409Fixture() throws {
        let json = """
        {"error":{"code":"EVALUATION_VERSION_CONFLICT","message":"The evaluation changed since it was loaded.","details":{},"request_id":"req-error-409"}}
        """.data(using: .utf8)!
        let envelope = try JSONDecoder().decode(APIErrorEnvelope.self, from: json)
        XCTAssertEqual(envelope.error.code, "EVALUATION_VERSION_CONFLICT")
    }

    func testNoForbiddenMetadataInReviewItemJSON() {
        let json = """
        {"session":{"id":"s1","current_cursor":0,"candidate_count":10},"position":0,"media":{"id":"m1","kind":"image","preview_url":"/p","playback_url":null,"width":1024,"height":1536,"duration_seconds":null},"prompts":[{"role":"positive","label":"Prompt","text":"A landscape"}],"evaluations":[{"id":"e1","evaluation_kind":"base","progress_state":"not_started","is_trash":false,"version":1,"criteria":[{"id":"c1","label":"Aesthetic","description":null,"min_value":0,"max_value":10}],"scores":[]}]}
        """
        let forbidden = ["filename", "sha256", "checkpoint", "lora", "workflow", "source_path", "model"]
        for term in forbidden {
            XCTAssertFalse(json.lowercased().contains(term), "JSON contains forbidden metadata: \(term)")
        }
    }
}
