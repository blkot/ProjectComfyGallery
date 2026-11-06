import Foundation

struct MediaNavigation: Decodable, Sendable {
    let mediaID: String
    let position: Int
    let total: Int
    let previousID: String?
    let nextID: String?

    enum CodingKeys: String, CodingKey {
        case mediaID = "media_id", position, total
        case previousID = "previous_id", nextID = "next_id"
    }
}
