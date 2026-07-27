import XCTest

@MainActor
final class ComfyGalleryXRUITests: XCTestCase {
    func testLibraryLaunches() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.staticTexts["Gallery"].waitForExistence(timeout: 5))
    }
}
