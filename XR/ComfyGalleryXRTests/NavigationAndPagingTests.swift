import XCTest
@testable import ComfyGalleryXR

final class NavigationAndPagingTests: XCTestCase {
    func testDragRequiresHorizontalThreshold() {
        XCTAssertNil(
            DragNavigationDecision.direction(
                translation: CGSize(width: 40, height: 4),
                predictedEndTranslation: CGSize(width: 50, height: 4),
                cardWidth: 900
            )
        )
        XCTAssertEqual(
            DragNavigationDecision.direction(
                translation: CGSize(width: -140, height: 10),
                predictedEndTranslation: CGSize(width: -190, height: 10),
                cardWidth: 900
            ),
            .next
        )
        XCTAssertEqual(
            DragNavigationDecision.direction(
                translation: CGSize(width: 130, height: 10),
                predictedEndTranslation: CGSize(width: 180, height: 10),
                cardWidth: 900
            ),
            .previous
        )
        XCTAssertNil(
            DragNavigationDecision.direction(
                translation: CGSize(width: 130, height: 200),
                predictedEndTranslation: CGSize(width: 200, height: 260),
                cardWidth: 900
            )
        )
    }

    func testPageDeduplicationPreservesRawOffset() {
        let firstID = UUID()
        let secondID = UUID()
        let existing = [summary(id: firstID)]
        let page = MediaPage(
            items: [summary(id: firstID), summary(id: secondID)],
            total: 10,
            limit: 2,
            offset: 1
        )
        let result = MediaPageAccumulator.accumulate(
            existing: existing,
            page: page,
            replacing: false
        )
        XCTAssertEqual(result.items.map(\.id), [firstID, secondID])
        XCTAssertEqual(result.rawOffset, 3)
        XCTAssertFalse(result.isExhausted)
    }

    func testImagePresentationScaleContainsImage() {
        XCTAssertEqual(
            ImagePresentationScaler.scale(
                presentationSize: SIMD2(2, 1),
                availableSize: SIMD2(1, 1)
            ),
            SIMD3(0.5, 0.5, 1)
        )
    }

    private func summary(id: UUID) -> XRMediaSummary {
        XRMediaSummary(
            id: id,
            kind: .image,
            status: "ready",
            mimeType: "image/png",
            width: 800,
            height: 1_200,
            durationSeconds: nil,
            byteSize: 1_000,
            isTrash: false,
            previewPath: "/preview"
        )
    }
}
