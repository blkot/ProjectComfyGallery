import Foundation

@main
struct ViewerRegressionChecks {
    static func main() throws {
        var checks = 0
        func check(_ condition: Bool, _ message: String) {
            guard condition else { print("FAIL: \(message)"); exit(1) }
            checks += 1
        }
        let a = try item("a"), b = try item("b", trash: true), c = try item("c")
        let navigation = MediaNavigation(mediaID: "c", position: 2, total: 2, previousID: "a", nextID: nil)
        let pages = ViewerPageWindow.reconcile(current: c, navigation: navigation, cached: [a, b, c], fetched: [])
        check(pages.map(\.id) == ["a", "c"], "Trash B, seek C: stale B must not block reverse seek")
        let back = MediaNavigation(mediaID: "a", position: 1, total: 2, previousID: nil, nextID: "c")
        check(ViewerPageWindow.reconcile(current: a, navigation: back, cached: pages, fetched: []).map(\.id) == ["a", "c"], "Reverse seek skips removed B")
        let beforeLeaving = MediaNavigation(mediaID: "b", position: 2, total: 3, previousID: "a", nextID: "c")
        check(ViewerPageWindow.reconcile(current: b, navigation: beforeLeaving, cached: [a, b, c], fetched: []).map(\.id) == ["a", "b", "c"], "Trash does not automatically advance the current item")
        check(ViewerPageWindow.reconcile(current: b, navigation: beforeLeaving, cached: [c, b, a, try item("old")], fetched: []).map(\.id) == ["a", "b", "c"], "Server order wins; history cannot accumulate beyond three pages")
        check(ViewerPageWindow.reconcile(current: a, navigation: nil, cached: [b, c], fetched: []).map(\.id) == ["a"], "Unknown navigation cannot leak cached history")

        let originalB = try item("b")
        let removal = LibraryMutationProjection(items: [a, originalB, c], updated: b, scope: GalleryScope())
        check(removal.items.map(\.id) == ["a", "c"], "Acknowledged trash is immediately removed from grid")
        check(removal.removedIndex == 1 && removal.fallbackAnchorID == "c", "Return anchor moves to nearest remaining item")
        check(LibraryMutationProjection(items: removal.items, updated: b, scope: GalleryScope()).removedIndex == nil, "Repeated update cannot decrement pagination twice")
        check(LibraryMutationProjection(items: [originalB], updated: b, scope: GalleryScope()).fallbackAnchorID == nil, "Last-item removal leaves no phantom anchor")
        check(LibraryMutationProjection(items: [a, originalB], updated: b, scope: GalleryScope()).fallbackAnchorID == "a", "Final-item anchor falls back to previous")
        check(LibraryMutationProjection(items: [a, originalB], updated: b, scope: GalleryScope(trash: .included)).items.count == 2, "Trash-inclusive scope retains trashed media")
        check(LibraryMutationProjection(items: [b], updated: originalB, scope: GalleryScope(trash: .only)).items.isEmpty, "Restore removes media from Trash-only grid")
        let prompt = GalleryScope(promptUsage: PromptUsageScope(promptID: "source - 001"))
        check(!LibraryMutationProjection(items: [originalB], updated: b, scope: prompt).items.isEmpty, "Prompt Usage still includes Trash according to its API")
        check(GalleryScope(favorite: .only).excludes(originalB), "Removing Favorite excludes media from Favorites scope")
        var rated = originalB
        rated.contentRating = "nsfw"
        check(GalleryScope(rating: .sfw).excludes(rated), "Rating mutation respects Content Safety scope")
        var grouped = originalB
        grouped.characterLora = "Alice"
        check(LibraryMutationProjection(items: [grouped], updated: b, scope: prompt).items.first?.characterLora == "Alice", "Detail refresh preserves Usage group identity")

        let policy = ViewerPagingPolicy()
        check(policy.lockedAxis(.undecided, translation: CGSize(width: 10, height: 8)) == .undecided, "Ignore initial jitter")
        check(policy.lockedAxis(.undecided, translation: CGSize(width: 20, height: -19)) == .vertical, "Ambiguous diagonal favors vertical")
        let vertical = policy.lockedAxis(.undecided, translation: CGSize(width: 5, height: -20))
        check(policy.lockedAxis(vertical, translation: CGSize(width: 220, height: -90)) == .vertical, "Once vertical, axis cannot become horizontal")
        check(policy.pageStep(axis: vertical, translation: CGSize(width: 220, height: -90), predicted: CGSize(width: 900, height: -100), width: 390) == 0, "Upward-origin swipe cannot turn a page")
        check(policy.verticalAction(axis: .vertical, translation: CGSize(width: 22, height: -100)) == .details, "Up-swipe opens details")
        check(policy.verticalAction(axis: .vertical, translation: CGSize(width: 20, height: 150)) == .dismiss, "Down-swipe dismisses")
        check(policy.pageStep(axis: .horizontal, translation: CGSize(width: -60, height: 0), predicted: CGSize(width: -60, height: 0), width: 390) == 0, "Short drag snaps back")
        check(policy.pageStep(axis: .horizontal, translation: CGSize(width: -100, height: 10), predicted: CGSize(width: -100, height: 0), width: 390) == 1, "24-percent-width drag advances one page")
        check(policy.pageStep(axis: .horizontal, translation: CGSize(width: -42, height: 5), predicted: CGSize(width: -300, height: 0), width: 390) == 1, "Intentional short flick advances one page")
        check(policy.pageStep(axis: .horizontal, translation: CGSize(width: -25, height: 0), predicted: CGSize(width: -2000, height: 0), width: 390) == 0, "Prediction alone cannot turn a page")
        check(policy.pageStep(axis: .horizontal, translation: CGSize(width: -42, height: 0), predicted: CGSize(width: 300, height: 0), width: 390) == 0, "Reversed short flick snaps back")
        check(policy.pageStep(axis: .horizontal, translation: CGSize(width: -100, height: -160), predicted: CGSize(width: -500, height: -300), width: 390) == 0, "Final upward motion cancels an early horizontal intention")
        check(policy.dragOffset(-1000, width: 390, hasNeighbor: true) == -390, "Film strip drag is limited to one viewport")
        check(policy.dragOffset(100, width: 390, hasNeighbor: false) == 18, "Boundary drag is resisted")
        for magnitude in 1...1000 {
            let x = CGFloat(magnitude) * 11
            let forward = policy.pageStep(axis: .horizontal, translation: CGSize(width: -x, height: 0), predicted: CGSize(width: -x * 8, height: 0), width: 390)
            let backward = policy.pageStep(axis: .horizontal, translation: CGSize(width: x, height: 0), predicted: CGSize(width: x * 8, height: 0), width: 390)
            check((0...1).contains(forward) && (-1...0).contains(backward), "Fast flick \(magnitude) cannot skip multiple pages")
        }
        print("PASS: \(checks) viewer regression checks (including 1,000 bidirectional flick traces)")
    }

    static func item(_ id: String, trash: Bool = false) throws -> MobileMediaSummary {
        try JSONDecoder().decode(MobileMediaSummary.self, from: Data("{\"id\":\"\(id)\",\"kind\":\"image\",\"preview_url\":\"/p\",\"is_trash\":\(trash)}".utf8))
    }
}
