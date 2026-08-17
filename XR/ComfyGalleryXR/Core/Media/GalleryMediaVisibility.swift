import Foundation

enum GalleryMediaVisibility {
    static func includes(status: String) -> Bool {
        switch status {
        case "ready", "ready_with_warnings":
            true
        default:
            false
        }
    }

    static func includes(_ media: XRMediaSummary) -> Bool {
        includes(status: media.status)
    }

    static func includes(_ media: XRMediaDetail) -> Bool {
        includes(status: media.status)
    }
}
