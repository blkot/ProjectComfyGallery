import Foundation

enum LibraryLayout {
    // Portrait 4:3 means width:height = 3:4.
    static let tileAspectRatio: CGFloat = 3.0 / 4.0
    static let spacing: CGFloat = 2

    static func columnCount(width: CGFloat, accessibilitySize: Bool) -> Int {
        if accessibilitySize { return max(2, Int(width / 220)) }
        return width < 600 ? 3 : max(4, Int(width / 150))
    }
}
