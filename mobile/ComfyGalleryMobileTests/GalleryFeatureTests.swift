import XCTest
@testable import ComfyGalleryMobile

@MainActor
final class GalleryFeatureTests: XCTestCase {
    func testDefaultPortraitLayoutAndPhoneColumns() {
        XCTAssertEqual(LibraryLayout.tileAspectRatio, 0.75)
        XCTAssertEqual(LibraryLayout.columnCount(width: 393, accessibilitySize: false), 3)
        XCTAssertEqual(LibraryLayout.columnCount(width: 393, accessibilitySize: true), 2)
        XCTAssertGreaterThanOrEqual(LibraryLayout.columnCount(width: 1024, accessibilitySize: false), 4)
    }

    func testSharedScopeIncludesAllFiltersButNoPaginationInNavigation() {
        let scope = GalleryScope(kind: .video, favorite: .only, trash: .included, rating: .sfw, sort: .fileOldest, query: "  ocean  ")
        let query = Dictionary(uniqueKeysWithValues: scope.queryItems.map { ($0.name, $0.value ?? "") })
        XCTAssertEqual(query["kind"], "video")
        XCTAssertEqual(query["favorite"], "true")
        XCTAssertEqual(query["content_rating"], "sfw")
        XCTAssertEqual(query["sort"], "file_created_asc")
        XCTAssertEqual(query["q"], "ocean")
        XCTAssertNil(query["trash"])
        XCTAssertEqual(Endpoint.mediaNavigation(id: "one", scope: scope).queryItems, scope.queryItems)
        XCTAssertFalse(scope.queryItems.contains { $0.name == "offset" })
    }

    func testLateResponseCannotOverwriteNewScope() async throws {
        let service = GalleryTestService()
        await service.holdNextPage()
        let feature = LibraryFeature(service: service)
        let old = Task { await feature.reload() }
        await service.waitForHeldPage()
        feature.scope.kind = .video
        await feature.reload()
        await service.releasePage()
        await old.value
        XCTAssertEqual(feature.items.map(\.id), ["video"])
        XCTAssertEqual(feature.loadedScope?.kind, .video)
        XCTAssertFalse(feature.isLoading)
    }

    func testPaginationDeduplicatesAndUsesServerOffset() async {
        let service = GalleryTestService()
        await service.useOverlappingPages()
        let feature = LibraryFeature(service: service)
        await feature.reload()
        await feature.loadMore()
        XCTAssertEqual(feature.items.map(\.id), ["one", "two", "three"])
        XCTAssertEqual(feature.nextOffset, 4)
        XCTAssertFalse(feature.canLoadMore)
    }

    func testStalePaginationCannotAppendToNewScope() async {
        let service = GalleryTestService()
        await service.useOverlappingPages()
        let feature = LibraryFeature(service: service)
        await feature.reload()
        await service.holdNextPage()
        let old = Task { await feature.loadMore() }
        await service.waitForHeldPage()
        feature.scope.kind = .video
        await feature.reload()
        await service.releasePage()
        await old.value
        XCTAssertEqual(feature.items.map(\.id), ["video"])
        XCTAssertFalse(feature.isLoadingMore)
    }

    func testFailedRefreshRetainsVisibleItems() async {
        let service = GalleryTestService()
        let feature = LibraryFeature(service: service)
        await feature.reload()
        await service.failPages()
        await feature.reload(preservingPosition: true)
        XCTAssertEqual(feature.items.map(\.id), ["one"])
        XCTAssertNotNil(feature.errorMessage)
    }

    func testChangingScopeClearsSelection() async {
        let feature = LibraryFeature(service: GalleryTestService())
        await feature.reload()
        feature.isSelecting = true
        feature.toggleSelection("one")
        feature.scope.kind = .video
        await feature.reload()
        XCTAssertTrue(feature.selectedIDs.isEmpty)
        XCTAssertFalse(feature.isSelecting)
    }

    func testPartialMutationReportsSkippedAndReloadsAuthoritativeState() async {
        let service = GalleryTestService()
        let feature = LibraryFeature(service: service)
        await feature.reload()
        feature.isSelecting = true
        feature.toggleSelection("one")
        let acknowledged = await feature.mutateSelection(favorite: true)
        XCTAssertTrue(acknowledged)
        XCTAssertEqual(feature.notice, "已更新 0 项，跳过 1 项")
        XCTAssertEqual(feature.items.first?.favorite, false)
        XCTAssertFalse(feature.isSelecting)
        let requestedIDs = await service.mutatedIDs
        XCTAssertEqual(requestedIDs, ["one"])
    }

    func testViewerStaysOnItemAfterRemovingFavorite() async {
        let service = GalleryTestService(favorite: true, applyMutations: true)
        let feature = ViewerFeature(item: GalleryTestService.item("one", favorite: true), scope: GalleryScope(favorite: .only), service: service)
        await feature.loadContext()
        await feature.mutate(favorite: false)
        XCTAssertEqual(feature.item.id, "one")
        XCTAssertTrue(feature.outsideScope)
        XCTAssertEqual(feature.item.favorite, false)
    }

    func testViewerDoesNotOpenItemOutsideScope() async {
        let service = GalleryTestService()
        let feature = ViewerFeature(item: GalleryTestService.item("one"), scope: GalleryScope(), service: service)
        await feature.loadContext()
        await feature.open(id: "missing")
        XCTAssertEqual(feature.item.id, "one")
        XCTAssertNotNil(feature.errorMessage)
    }

    func testViewerPreparesOnlyImmediateNeighborPages() async {
        let feature = ViewerFeature(item: GalleryTestService.item("one"), scope: GalleryScope(), service: GalleryTestService())
        await feature.loadContext()
        XCTAssertEqual(feature.pages.map(\.id), ["one", "two"])
        XCTAssertEqual(feature.neighbors.map(\.id), ["two"])
    }

    func testRatingChangeKeepsCurrentMediaEvenWhenItLeavesFilter() async {
        let feature = ViewerFeature(item: GalleryTestService.item("one"), scope: GalleryScope(rating: .sfw), service: GalleryTestService())
        await feature.loadContext()
        await feature.mutate(rating: "nsfw")
        XCTAssertEqual(feature.item.id, "one")
        XCTAssertEqual(feature.item.contentRating, "nsfw")
        XCTAssertTrue(feature.outsideScope)
    }

    func testPromptViewerRetainsUsageScope() async {
        let service = GalleryTestService()
        let prompt = PromptUsageScope(promptID: "portrait - 00042", characterLora: "Alice")
        let feature = ViewerFeature(item: GalleryTestService.item("one"), scope: GalleryScope(promptUsage: prompt), service: service)
        await feature.loadContext()
        let passedScope = await service.lastNavigationScope
        XCTAssertEqual(passedScope?.promptUsage, prompt)
        XCTAssertFalse(feature.outsideScope)
    }

    func testScopeChangeClearsOldSelectionBeforeLoadingNewData() async {
        let feature = LibraryFeature(service: GalleryTestService())
        await feature.reload()
        feature.toggleSelection("one")
        feature.scope.characterLora = "Alice"
        XCTAssertTrue(feature.items.isEmpty)
        XCTAssertTrue(feature.selectedIDs.isEmpty)
        XCTAssertNil(feature.loadedScope)
    }
}

private actor GalleryTestService: GalleryService {
    private var holdPage = false
    private var continuation: CheckedContinuation<Void, Never>?
    private var waiters: [CheckedContinuation<Void, Never>] = []
    private var overlapping = false
    private var pagesFail = false
    private var favorite: Bool
    private var rating = "sfw"
    private(set) var lastNavigationScope: GalleryScope?
    private let applyMutations: Bool
    private(set) var mutatedIDs: [String] = []

    init(favorite: Bool = false, applyMutations: Bool = false) {
        self.favorite = favorite
        self.applyMutations = applyMutations
    }

    func holdNextPage() { holdPage = true }
    func useOverlappingPages() { overlapping = true }
    func failPages() { pagesFail = true }
    func waitForHeldPage() async {
        if continuation != nil { return }
        await withCheckedContinuation { waiters.append($0) }
    }
    func releasePage() { continuation?.resume(); continuation = nil }

    func page(scope: GalleryScope, limit: Int, offset: Int) async throws -> MediaPage {
        if holdPage {
            holdPage = false
            await withCheckedContinuation { continuation = $0; waiters.forEach { $0.resume() }; waiters = [] }
        }
        if pagesFail { throw APIError.serverError(503) }
        if scope.kind == .video { return MediaPage(items: [Self.item("video", kind: .video)], total: 1, limit: limit, offset: offset) }
        let ids = overlapping ? (offset == 0 ? ["one", "two"] : ["two", "three"]) : ["one"]
        return MediaPage(items: ids.map { Self.item($0) }, total: overlapping ? 4 : 1, limit: limit, offset: offset)
    }

    func detail(id: String) async throws -> MobileMediaSummary {
        var media = Self.item(id, favorite: favorite)
        media.contentRating = rating
        return media
    }
    func navigation(id: String, scope: GalleryScope) async throws -> MediaNavigation {
        lastNavigationScope = scope
        if id == "missing" { throw APIError.notFound }
        return MediaNavigation(mediaID: id, position: id == "one" ? 1 : 2, total: 2, previousID: id == "one" ? nil : "one", nextID: id == "one" ? "two" : nil)
    }
    func setContentRating(id: String, rating: String) async throws { self.rating = rating }
    func setFavorite(ids: [String], value: Bool) async throws -> MediaBulkResult {
        mutatedIDs = ids
        if applyMutations { favorite = value }
        return MediaBulkResult(requestedCount: ids.count, updatedCount: 0, skippedCount: ids.count, errors: [])
    }
    func setTrash(ids: [String], value: Bool) async throws -> MediaBulkResult {
        mutatedIDs = ids
        return MediaBulkResult(requestedCount: ids.count, updatedCount: 0, skippedCount: ids.count, errors: [])
    }
    nonisolated static func item(_ id: String, kind: MediaKind = .image, favorite: Bool = false) -> MobileMediaSummary {
        MobileMediaSummary(id: id, kind: kind, evaluationState: nil, isTrash: false, previewURL: "/preview", favorite: favorite, width: 1200, height: 1600, durationSeconds: nil, fileCreatedAt: nil, createdAt: nil)
    }
}
