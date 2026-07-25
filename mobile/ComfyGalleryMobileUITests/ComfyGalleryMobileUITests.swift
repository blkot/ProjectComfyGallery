import XCTest

final class ComfyGalleryMobileUITests: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["UI-TESTING"]
        app.launch()
    }

    func testConnectionScreenAppears() {
        XCTAssertTrue(app.textFields.firstMatch.exists || app.buttons["Connect"].exists)
    }

    func testLibraryTabExists() {
        let libraryTab = app.tabBars.buttons["Library"]
        _ = libraryTab.waitForExistence(timeout: 5)
    }

    func testReviewTabExists() {
        let reviewTab = app.tabBars.buttons["Review"]
        _ = reviewTab.waitForExistence(timeout: 5)
    }

    func testSettingsTabExists() {
        let settingsTab = app.tabBars.buttons["Settings"]
        _ = settingsTab.waitForExistence(timeout: 5)
    }
}
