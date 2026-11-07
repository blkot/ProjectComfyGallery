import Foundation
import Observation

@MainActor
@Observable
final class ViewerFeature {
    private(set) var item: MobileMediaSummary
    private(set) var pages: [MobileMediaSummary]
    private(set) var navigation: MediaNavigation?
    private(set) var isWorking = false
    private(set) var isMutating = false
    private(set) var canMutate = false
    var errorMessage: String?
    let scope: GalleryScope
    private let service: any GalleryService
    private var generation = 0

    init(item: MobileMediaSummary, scope: GalleryScope, service: any GalleryService) {
        self.item = item
        self.pages = [item]
        self.scope = scope
        self.service = service
    }

    var outsideScope: Bool {
        scope.excludes(item)
    }

    var neighbors: [MobileMediaSummary] {
        [navigation?.previousID, navigation?.nextID].compactMap { id in pages.first { $0.id == id } }
    }

    var prefetchKey: String { ([item.id] + neighbors.map(\.id)).joined(separator: "|") }

    func loadContext() async {
        guard !isWorking else { return }
        generation += 1
        let request = generation
        isWorking = true
        errorMessage = nil
        canMutate = false
        defer { if request == generation { isWorking = false } }
        do {
            let detail = try await service.detail(id: item.id)
            let context = scope.excludes(detail) ? navigation : try await service.navigation(id: detail.id, scope: scope)
            try Task.checkCancellation()
            guard request == generation else { return }
            item = detail
            navigation = context
            canMutate = true
            replacePage(item)
            await loadNeighbors(generation: request)
        } catch {
            if !Task.isCancelled, request == generation { errorMessage = error.localizedDescription }
        }
    }

    func open(id: String) async {
        guard !isMutating, id != item.id else { return }
        generation += 1
        let request = generation
        isWorking = true
        errorMessage = nil
        defer { if request == generation { isWorking = false } }
        do {
            // Validate membership before replacing the current page.
            let context = try await service.navigation(id: id, scope: scope)
            let detail = try await service.detail(id: id)
            try Task.checkCancellation()
            guard request == generation else { return }
            item = detail
            navigation = context
            canMutate = true
            replacePage(detail)
            await loadNeighbors(generation: request)
        } catch {
            if !Task.isCancelled, request == generation { errorMessage = "无法切换：\(error.localizedDescription) 可关闭查看器并刷新图库。" }
        }
    }

    func mutate(favorite: Bool? = nil, trash: Bool? = nil, rating: String? = nil) async {
        guard !isWorking, canMutate else { return }
        isWorking = true
        isMutating = true
        errorMessage = nil
        defer { isWorking = false; isMutating = false }
        do {
            let result: MediaBulkResult?
            if let favorite { result = try await service.setFavorite(ids: [item.id], value: favorite) }
            else if let trash { result = try await service.setTrash(ids: [item.id], value: trash) }
            else if let rating {
                try await service.setContentRating(id: item.id, rating: rating)
                result = nil
            }
            else { return }
            canMutate = false
            item = try await service.detail(id: item.id)
            canMutate = true
            replacePage(item)
            // Keep showing this item even when the mutation removes it from the filter.
            if !outsideScope { navigation = try await service.navigation(id: item.id, scope: scope) }
            await loadNeighbors(generation: generation)
            if let result, !result.errors.isEmpty { errorMessage = result.message }
        } catch {
            canMutate = false
            errorMessage = "操作状态待确认：\(error.localizedDescription) 请刷新确认后重试。"
        }
    }

    private func replacePage(_ detail: MobileMediaSummary) {
        if let index = pages.firstIndex(where: { $0.id == detail.id }) { pages[index] = detail }
        else { pages.append(detail) }
    }

    private func loadNeighbors(generation request: Int) async {
        let center = item.id
        let previous = navigation?.previousID
        let next = navigation?.nextID
        var fetched: [MobileMediaSummary] = []
        // Metadata only; heavy resource preloading is bounded separately by MediaRepository.
        for id in [previous, next].compactMap({ $0 }) {
            guard !pages.contains(where: { $0.id == id }) else { continue }
            guard let detail = try? await service.detail(id: id), !Task.isCancelled,
                  request == generation, item.id == center else { continue }
            fetched.append(detail)
        }
        guard !Task.isCancelled, request == generation, item.id == center else { return }
        pages = ViewerPageWindow.reconcile(current: item, navigation: navigation, cached: pages, fetched: fetched)
    }
}
