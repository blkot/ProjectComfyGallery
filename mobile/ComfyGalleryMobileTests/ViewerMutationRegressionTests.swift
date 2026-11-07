import XCTest
@testable import ComfyGalleryMobile

@MainActor
final class ViewerMutationRegressionTests: XCTestCase {
    func testTrashThenForwardThenBackwardDoesNotReinsertDeletedPage() async throws {
        let service = ViewerMutationService()
        let viewer = ViewerFeature(item: try await service.detail(id: "b"), scope: GalleryScope(), service: service)
        await viewer.loadContext()
        XCTAssertEqual(viewer.pages.map(\.id), ["a", "b", "c"])
        await viewer.mutate(trash: true)
        XCTAssertEqual(viewer.item.id, "b", "Trash must not auto-advance")
        await viewer.open(id: "c")
        XCTAssertEqual(viewer.pages.map(\.id), ["a", "c"])
        XCTAssertEqual(viewer.navigation?.previousID, "a")
        await viewer.open(id: "a")
        XCTAssertEqual(viewer.item.id, "a")
        XCTAssertEqual(viewer.pages.map(\.id), ["a", "c"])
        XCTAssertNil(viewer.errorMessage)
    }

    func testTrashUpdatesGridCountsAndAnchorBeforeAnyReload() async throws {
        let service = ViewerMutationService()
        let library = LibraryFeature(service: service)
        await library.reload()
        library.returnAnchorID = "b"
        library.toggleSelection("b")
        _ = try await service.setTrash(ids: ["b"], value: true)
        let detail = try await service.detail(id: "b")
        library.update(detail)
        XCTAssertEqual(library.items.map(\.id), ["a", "c"])
        XCTAssertEqual(library.total, 2)
        XCTAssertEqual(library.nextOffset, 2)
        XCTAssertEqual(library.returnAnchorID, "c")
        XCTAssertTrue(library.selectedIDs.isEmpty)
        XCTAssertTrue(library.needsRefresh)
        library.update(detail)
        XCTAssertEqual(library.total, 2, "Repeated detail delivery must not remove twice")
    }

    func testPreMutationRefreshCannotReinsertTrash() async throws {
        let service = ViewerMutationService()
        let library = LibraryFeature(service: service)
        await library.reload()
        await service.holdNextPage()
        let stale = Task { await library.reload(preservingPosition: true) }
        await service.waitForHeldPage()
        _ = try await service.setTrash(ids: ["b"], value: true)
        library.update(try await service.detail(id: "b"))
        await service.releasePage()
        await stale.value
        XCTAssertEqual(library.items.map(\.id), ["a", "c"])
        XCTAssertEqual(library.total, 2)
        XCTAssertTrue(library.needsRefresh)
    }

    func testPromptUsageKeepsTrashAndUsesItsOwnNavigation() async throws {
        let service = ViewerMutationService()
        let scope = GalleryScope(promptUsage: PromptUsageScope(promptID: "source - 001"))
        let viewer = ViewerFeature(item: try await service.detail(id: "b"), scope: scope, service: service)
        await viewer.loadContext()
        await viewer.mutate(trash: true)
        await viewer.open(id: "c")
        XCTAssertEqual(viewer.navigation?.previousID, "b")
        XCTAssertFalse(viewer.outsideScope)
    }

    func testFailedMutationDoesNotRemoveMediaFromGrid() async throws {
        let service = ViewerMutationService()
        let library = LibraryFeature(service: service)
        await library.reload()
        let viewer = ViewerFeature(item: try await service.detail(id: "b"), scope: GalleryScope(), service: service)
        await viewer.loadContext()
        await service.failMutations()
        await viewer.mutate(trash: true)
        library.update(viewer.item)
        XCTAssertEqual(library.items.map(\.id), ["a", "b", "c"])
        XCTAssertNotNil(viewer.errorMessage)
    }

    func testFavoriteAndRatingAreAcknowledgedByStateWithoutAnError() async throws {
        let service = ViewerMutationService()
        let viewer = ViewerFeature(item: try await service.detail(id: "b"), scope: GalleryScope(), service: service)
        await viewer.loadContext()
        await viewer.mutate(favorite: true)
        XCTAssertEqual(viewer.item.favorite, true)
        await viewer.mutate(favorite: false)
        XCTAssertEqual(viewer.item.favorite, false)
        await viewer.mutate(rating: "nsfw")
        XCTAssertEqual(viewer.item.contentRating, "nsfw")
        XCTAssertNil(viewer.errorMessage)
    }
}

private actor ViewerMutationService: GalleryService {
    private var trashed: Set<String> = []
    private var favorites: Set<String> = []
    private var ratings: [String: String] = [:]
    private var failWrites = false
    private var holdPage = false
    private var heldPage: CheckedContinuation<Void, Never>?
    private var pageWaiters: [CheckedContinuation<Void, Never>] = []

    func holdNextPage() { holdPage = true }
    func failMutations() { failWrites = true }
    func waitForHeldPage() async {
        if heldPage != nil { return }
        await withCheckedContinuation { pageWaiters.append($0) }
    }
    func releasePage() { heldPage?.resume(); heldPage = nil }

    func page(scope: GalleryScope, limit: Int, offset: Int) async throws -> MediaPage {
        // Capture before suspension to reproduce a genuinely stale server response.
        let items = visible(scope)
        if holdPage {
            holdPage = false
            await withCheckedContinuation {
                heldPage = $0
                pageWaiters.forEach { $0.resume() }
                pageWaiters = []
            }
        }
        return MediaPage(items: Array(items.dropFirst(offset).prefix(limit)), total: items.count, limit: limit, offset: offset)
    }

    func detail(id: String) throws -> MobileMediaSummary {
        guard ["a", "b", "c"].contains(id) else { throw APIError.notFound }
        return media(id)
    }

    func navigation(id: String, scope: GalleryScope) throws -> MediaNavigation {
        let items = visible(scope)
        guard let index = items.firstIndex(where: { $0.id == id }) else { throw APIError.notFound }
        return MediaNavigation(mediaID: id, position: index + 1, total: items.count,
                               previousID: index > 0 ? items[index - 1].id : nil,
                               nextID: index + 1 < items.count ? items[index + 1].id : nil)
    }

    func setFavorite(ids: [String], value: Bool) throws -> MediaBulkResult {
        guard !failWrites else { throw APIError.serverError(503) }
        if value { favorites.formUnion(ids) } else { favorites.subtract(ids) }
        return result(ids)
    }

    func setTrash(ids: [String], value: Bool) throws -> MediaBulkResult {
        guard !failWrites else { throw APIError.serverError(503) }
        if value { trashed.formUnion(ids) } else { trashed.subtract(ids) }
        return result(ids)
    }

    func setContentRating(id: String, rating: String) throws {
        guard !failWrites else { throw APIError.serverError(503) }
        ratings[id] = rating
    }

    private func visible(_ scope: GalleryScope) -> [MobileMediaSummary] {
        ["a", "b", "c"].map(media).filter { !scope.excludes($0) }
    }

    private func media(_ id: String) -> MobileMediaSummary {
        var item = MobileMediaSummary(id: id, kind: .image, evaluationState: nil, isTrash: trashed.contains(id),
                                     previewURL: "/preview", favorite: favorites.contains(id), width: 1200, height: 1600,
                                     durationSeconds: nil, fileCreatedAt: nil, createdAt: nil)
        item.contentRating = ratings[id] ?? "sfw"
        return item
    }

    private func result(_ ids: [String]) -> MediaBulkResult {
        MediaBulkResult(requestedCount: ids.count, updatedCount: ids.count, skippedCount: 0, errors: [])
    }
}
