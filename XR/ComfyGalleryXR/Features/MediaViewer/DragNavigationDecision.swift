import CoreGraphics

enum NavigationDirection: Sendable {
    case previous
    case next
}
enum DragNavigationDecision {
    static func direction(
        translation: CGSize,
        predictedEndTranslation: CGSize,
        cardWidth: CGFloat
    ) -> NavigationDirection? {
        guard abs(translation.width) > abs(translation.height) else { return nil }
        let threshold = min(120, max(60, cardWidth * 0.2))
        let projected = abs(predictedEndTranslation.width) > abs(translation.width)
            ? predictedEndTranslation.width
            : translation.width
        guard abs(translation.width) >= threshold || abs(projected) >= threshold * 1.35 else {
            return nil
        }
        return projected < 0 ? .next : .previous
    }
}
