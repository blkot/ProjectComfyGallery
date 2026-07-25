import XCTest
@testable import ComfyGalleryMobile

final class VideoCacheTests: XCTestCase {
    func testCacheMissReturnsNil() async {
        let cache = VideoCache()
        let url = await cache.cachedURL(for: "nonexistent")
        XCTAssertNil(url)
    }

    func testCurrentSizeStartsAtZero() async {
        let cache = VideoCache()
        let size = await cache.currentSize
        XCTAssertEqual(size, 0)
    }
}
