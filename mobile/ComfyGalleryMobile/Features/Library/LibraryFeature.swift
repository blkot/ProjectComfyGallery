import Foundation
import Observation

@MainActor
@Observable
final class LibraryFeature {
    private(set) var items: [MobileMediaSummary] = [] {
        didSet { sections = MediaDaySection.group(items, sort: scope.sort, byCharacter: scope.promptUsage != nil) }
    }
    private(set) var sections: [MediaDaySection] = []
    private(set) var total = 0
    private(set) var nextOffset = 0
    private(set) var isLoading = false
    private(set) var isLoadingMore = false
    private(set) var isMutating = false
    private(set) var loadedScope: GalleryScope?
    var scope: GalleryScope {
        didSet {
            guard scope != oldValue else { return }
            generation += 1
            items = []
            total = 0
            nextOffset = 0
            loadedScope = nil
            errorMessage = nil
            paginationError = nil
            notice = nil
            returnAnchorID = nil
            isLoading = false
            isLoadingMore = false
            endSelection()
        }
    }
    var errorMessage: String?
    var paginationError: String?
    var notice: String?
    var selectedIDs: Set<String> = []
    var isSelecting = false
    var returnAnchorID: String?
    var needsRefresh = false

    let service: any GalleryService
    private let pageSize = 48
    private var generation = 0
    private var exhausted = false

    init(service: any GalleryService, scope: GalleryScope = GalleryScope()) {
        self.service = service
        self.scope = scope
    }

    var canLoadMore: Bool { !exhausted && nextOffset < total }
    var selectedItems: [MobileMediaSummary] { items.filter { selectedIDs.contains($0.id) } }
    var allSelectedAreFavorites: Bool { !selectedItems.isEmpty && selectedItems.allSatisfy { $0.favorite == true } }

    func reload(preservingPosition: Bool = false) async {
        generation += 1
        let requestGeneration = generation
        let requestedScope = scope
        let previousAnchorIndex = returnAnchorID.flatMap { id in items.firstIndex { $0.id == id } }
        let targetCount = preservingPosition && loadedScope == scope ? max(pageSize, nextOffset) : pageSize
        if loadedScope != scope {
            items = []
            total = 0
            nextOffset = 0
            returnAnchorID = nil
            endSelection()
        }
        isLoading = true
        isLoadingMore = false
        errorMessage = nil
        paginationError = nil
        defer { if generation == requestGeneration { isLoading = false } }
        do {
            var result: [MobileMediaSummary] = []
            var offset = 0
            var serverTotal = 0
            var reachedEnd = false
            repeat {
                let page = try await service.page(scope: requestedScope, limit: pageSize, offset: offset)
                try Task.checkCancellation()
                guard generation == requestGeneration, scope == requestedScope else { return }
                result = Self.merging(result, with: page.items)
                offset += page.items.count
                serverTotal = page.total
                reachedEnd = page.items.isEmpty || offset >= serverTotal
            } while offset < targetCount && !reachedEnd
            items = result
            total = serverTotal
            nextOffset = offset
            exhausted = reachedEnd
            loadedScope = requestedScope
            needsRefresh = false
            selectedIDs.formIntersection(Set(items.map(\.id)))
            if let anchor = returnAnchorID, !items.contains(where: { $0.id == anchor }) {
                returnAnchorID = items.isEmpty ? nil : items[min(previousAnchorIndex ?? 0, items.count - 1)].id
            }
        } catch {
            guard generation == requestGeneration, scope == requestedScope, !Task.isCancelled else { return }
            errorMessage = error.localizedDescription
        }
    }

    func loadMoreIfNeeded(id: String) async {
        guard let index = items.firstIndex(where: { $0.id == id }), index >= items.count - 12 else { return }
        await loadMore()
    }

    func loadMore() async {
        guard !isLoading, !isLoadingMore, loadedScope == scope, canLoadMore else { return }
        isLoadingMore = true
        paginationError = nil
        let requestGeneration = generation
        let requestedScope = scope
        let offset = nextOffset
        defer { if generation == requestGeneration { isLoadingMore = false } }
        do {
            let page = try await service.page(scope: requestedScope, limit: pageSize, offset: offset)
            try Task.checkCancellation()
            guard generation == requestGeneration, scope == requestedScope else { return }
            items = Self.merging(items, with: page.items)
            // Offset counts server records, not the deduplicated visible items.
            nextOffset = offset + page.items.count
            total = page.total
            exhausted = page.items.isEmpty || nextOffset >= total
        } catch {
            guard generation == requestGeneration, scope == requestedScope, !Task.isCancelled else { return }
            paginationError = error.localizedDescription
        }
    }

    func toggleSelection(_ id: String) {
        guard !isMutating else { return }
        if selectedIDs.contains(id) { selectedIDs.remove(id) }
        else if selectedIDs.count < 2000 { selectedIDs.insert(id) }
        else { notice = "每次最多选择 2,000 项。" }
    }

    func selectLoadedItems() { selectedIDs = Set(items.prefix(2000).map(\.id)) }

    func endSelection() {
        selectedIDs = []
        isSelecting = false
    }

    /// Explicit IDs only: selecting loaded items never silently selects the entire server library.
    func mutateSelection(favorite: Bool? = nil, trash: Bool? = nil) async -> Bool {
        guard !isMutating, !selectedIDs.isEmpty else { return false }
        let ids = selectedIDs.sorted()
        isMutating = true
        defer { isMutating = false }
        do {
            let result: MediaBulkResult
            if let favorite { result = try await service.setFavorite(ids: ids, value: favorite) }
            else if let trash { result = try await service.setTrash(ids: ids, value: trash) }
            else { return false }
            notice = result.message
            endSelection()
            await reload(preservingPosition: true)
            return true
        } catch {
            notice = "操作未确认：\(error.localizedDescription) 请刷新确认状态后再重试。"
            return false
        }
    }

    func update(_ item: MobileMediaSummary) {
        // A pre-mutation refresh/page response may still be in flight. It must not
        // reinsert a media item after its acknowledged removal from this scope.
        generation += 1
        isLoading = false
        isLoadingMore = false
        let projection = LibraryMutationProjection(items: items, updated: item, scope: scope)
        items = projection.items
        if projection.removedIndex != nil {
            total = max(0, total - 1)
            nextOffset = max(0, nextOffset - 1)
            exhausted = nextOffset >= total
            selectedIDs.remove(item.id)
            if returnAnchorID == item.id { returnAnchorID = projection.fallbackAnchorID }
        }
        needsRefresh = true
    }

    func rememberViewed(_ item: MobileMediaSummary) async {
        returnAnchorID = item.id
        if !items.contains(where: { $0.id == item.id }) { await loadMore() }
        await loadMoreIfNeeded(id: item.id)
    }

    private static func merging(_ existing: [MobileMediaSummary], with incoming: [MobileMediaSummary]) -> [MobileMediaSummary] {
        var seen = Set(existing.map(\.id))
        return existing + incoming.filter { seen.insert($0.id).inserted }
    }
}
