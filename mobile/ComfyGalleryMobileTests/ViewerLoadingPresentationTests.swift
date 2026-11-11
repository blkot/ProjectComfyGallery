import XCTest
@testable import ComfyGalleryMobile

@MainActor
final class ViewerLoadingPresentationTests: XCTestCase {
    func testFastCachedPageDoesNotFlashProgress() {
        let presentation = ViewerLoadingPresentation(revealDelay: .milliseconds(200))

        let request = presentation.begin()
        XCTAssertFalse(presentation.isVisible)

        presentation.finish(request)

        XCTAssertFalse(presentation.isVisible)
    }

    func testSlowPageShowsProgressAfterRevealDelay() async throws {
        let presentation = ViewerLoadingPresentation(revealDelay: .milliseconds(40))
        let request = presentation.begin()

        XCTAssertFalse(presentation.isVisible)
        try await Task.sleep(for: .milliseconds(100))
        XCTAssertTrue(presentation.isVisible)

        presentation.finish(request)

        XCTAssertFalse(presentation.isVisible)
    }

    func testFinishingStalePageDoesNotHideCurrentPageProgress() async throws {
        let presentation = ViewerLoadingPresentation(revealDelay: .milliseconds(40))
        let staleRequest = presentation.begin()
        let currentRequest = presentation.begin()

        presentation.finish(staleRequest)
        XCTAssertFalse(presentation.isVisible)

        try await Task.sleep(for: .milliseconds(100))
        XCTAssertTrue(presentation.isVisible)

        presentation.finish(currentRequest)

        XCTAssertFalse(presentation.isVisible)
    }
}
