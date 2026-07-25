import XCTest
@testable import ComfyGalleryMobile

final class APIErrorTests: XCTestCase {
    func testMap401ReturnsUnauthorized() {
        let error = APIError.map(statusCode: 401, envelope: nil)
        if case .unauthorized = error { } else { XCTFail("Expected .unauthorized") }
    }

    func testMap409ReturnsConflictWithEnvelope() {
        let envelope = APIErrorEnvelope(error: .init(code: "EVALUATION_VERSION_CONFLICT", message: "Changed since loaded.", details: nil, requestId: "req-123"))
        let error = APIError.map(statusCode: 409, envelope: envelope)
        if case .conflict(let e) = error {
            XCTAssertEqual(e.error.code, "EVALUATION_VERSION_CONFLICT")
            XCTAssertEqual(e.error.requestId, "req-123")
        } else { XCTFail("Expected .conflict") }
    }

    func testMap500ReturnsServerError() {
        let error = APIError.map(statusCode: 500, envelope: nil)
        if case .serverError(let code) = error { XCTAssertEqual(code, 500) }
        else { XCTFail("Expected .serverError") }
    }

    func testRetryableErrors() {
        XCTAssertTrue(APIError.serverError(500).isRetryable)
        XCTAssertTrue(APIError.networkError("test").isRetryable)
        XCTAssertFalse(APIError.unauthorized.isRetryable)
    }

    func testRequiresReauthentication() {
        XCTAssertTrue(APIError.unauthorized.requiresReauthentication)
        XCTAssertTrue(APIError.forbidden.requiresReauthentication)
        XCTAssertFalse(APIError.notFound.requiresReauthentication)
    }
}
