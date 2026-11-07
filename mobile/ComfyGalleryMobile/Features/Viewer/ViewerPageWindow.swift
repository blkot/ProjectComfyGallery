import Foundation

/// Reconciles the rendered pages with the server's current neighbor identities.
enum ViewerPageWindow {
    static func reconcile(current: MobileMediaSummary, navigation: MediaNavigation?,
                          cached: [MobileMediaSummary], fetched: [MobileMediaSummary]) -> [MobileMediaSummary] {
        let candidates = [current] + fetched + cached
        var seen: Set<String> = []
        // Navigation is authoritative, not the order of previously visited pages.
        // Keep an out-of-scope current item until the user explicitly leaves it.
        return [navigation?.previousID, current.id, navigation?.nextID].compactMap { id in
            guard let id, seen.insert(id).inserted else { return nil }
            return candidates.first { $0.id == id }
        }
    }
}
