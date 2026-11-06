import Foundation

enum ViewerPreloadPolicy {
    static let maximumVideoBytes: Int64 = 32 * 1024 * 1024
    static let maximumImagePixels: CGFloat = 2560

    static func neighbors(currentID: String, candidates: [MobileMediaSummary]) -> [MobileMediaSummary] {
        var seen = Set([currentID])
        return Array(candidates.filter { seen.insert($0.id).inserted }.prefix(2))
    }

    static func preloadVideo(_ item: MobileMediaSummary) -> Bool {
        guard item.kind == .video, let bytes = item.byteSize else { return false }
        return bytes > 0 && bytes <= maximumVideoBytes
    }
}
