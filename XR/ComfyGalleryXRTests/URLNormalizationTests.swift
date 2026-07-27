import XCTest
@testable import ComfyGalleryXR

final class URLNormalizationTests: XCTestCase {
    func testRejectsQuery() {
        XCTAssertThrowsError(
            try BaseURLNormalizer.normalize("https://gallery.local/api?ignored=no")
        )
    }

    func testNormalizesHostAndPath() throws {
        let url = try BaseURLNormalizer.normalize("HTTP://Gallery.Local:8181/api/v1")
        XCTAssertEqual(url.absoluteString, "http://gallery.local:8181/")
    }

    func testRejectsCredentials() {
        XCTAssertThrowsError(
            try BaseURLNormalizer.normalize("https://user:secret@gallery.local")
        )
    }

    func testSameOriginUsesDefaultPorts() throws {
        let lhs = try XCTUnwrap(URL(string: "https://gallery.local/a"))
        let rhs = try XCTUnwrap(URL(string: "https://gallery.local:443/b"))
        XCTAssertTrue(BaseURLNormalizer.isSameOrigin(lhs, rhs))
    }
}
