import Foundation

struct MediaPageAccumulationResult: Sendable {
    let items: [XRMediaSummary]
    let rawOffset: Int
    let isExhausted: Bool
}
enum MediaPageAccumulator {
    static func accumulate(
        existing: [XRMediaSummary],
        page: MediaPage,
        replacing: Bool
    ) -> MediaPageAccumulationResult {
        var seen = replacing ? Set<UUID>() : Set(existing.map(\.id))
        var items = replacing ? [] : existing
        for item in page.items where seen.insert(item.id).inserted {
            items.append(item)
        }
        let rawOffset = page.offset + page.items.count
        return MediaPageAccumulationResult(
            items: items,
            rawOffset: rawOffset,
            isExhausted: page.items.count < page.limit || rawOffset >= page.total
        )
    }
}
