import Foundation

/// Projects an acknowledged detail into the visible list without waiting for a reload.
struct LibraryMutationProjection {
    let items: [MobileMediaSummary]
    let removedIndex: Int?

    init(items: [MobileMediaSummary], updated: MobileMediaSummary, scope: GalleryScope) {
        var result = items
        var removed: Int?
        if let index = result.firstIndex(where: { $0.id == updated.id }) {
            if scope.excludes(updated) {
                result.remove(at: index)
                removed = index
            } else {
                var detail = updated
                // Detail responses lack the Usage-only character field.
                if detail.characterLora == nil { detail.characterLora = result[index].characterLora }
                result[index] = detail
            }
        }
        self.items = result
        removedIndex = removed
    }

    var fallbackAnchorID: String? {
        guard let removedIndex, !items.isEmpty else { return nil }
        return items[min(removedIndex, items.count - 1)].id
    }
}
