import Foundation

/// Shared by the actual pager and deterministic drag-trace regressions. Values are points.
struct ViewerPagingPolicy: Sendable {
    enum Axis: Sendable { case undecided, horizontal, vertical }
    enum VerticalAction { case none, details, dismiss }

    var intentDistance: CGFloat = 14
    var horizontalDominance: CGFloat = 1.6
    var pageFraction: CGFloat = 0.24
    var minimumPageDistance: CGFloat = 64
    var minimumFlickDistance: CGFloat = 40
    var flickPredictionFraction: CGFloat = 0.55
    var detailsDistance: CGFloat = 65
    var dismissDistance: CGFloat = 130

    func lockedAxis(_ axis: Axis, translation: CGSize) -> Axis {
        guard axis == .undecided else { return axis }
        let x = abs(translation.width), y = abs(translation.height)
        guard max(x, y) >= intentDistance else { return .undecided }
        // Ambiguous diagonal movement belongs to vertical browsing, never horizontal paging.
        return x >= y * horizontalDominance ? .horizontal : .vertical
    }

    func pageStep(axis: Axis, translation: CGSize, predicted: CGSize, width: CGFloat) -> Int {
        guard axis == .horizontal, width > 0,
              abs(translation.width) >= abs(translation.height) * horizontalDominance else { return 0 }
        let distance = abs(translation.width)
        let crossedDistance = distance >= max(minimumPageDistance, width * pageFraction)
        let flick = distance >= minimumFlickDistance &&
            translation.width * predicted.width > 0 && abs(predicted.width) >= width * flickPredictionFraction
        guard crossedDistance || flick else { return 0 }
        // Prediction decides whether to commit, never how many pages to skip.
        return translation.width < 0 ? 1 : -1
    }

    func verticalAction(axis: Axis, translation: CGSize) -> VerticalAction {
        guard axis == .vertical, abs(translation.height) > abs(translation.width) * 1.4 else { return .none }
        if translation.height < -detailsDistance { return .details }
        if translation.height > dismissDistance { return .dismiss }
        return .none
    }

    func dragOffset(_ translation: CGFloat, width: CGFloat, hasNeighbor: Bool) -> CGFloat {
        let bounded = max(-width, min(width, translation))
        return hasNeighbor ? bounded : bounded * 0.18
    }
}
