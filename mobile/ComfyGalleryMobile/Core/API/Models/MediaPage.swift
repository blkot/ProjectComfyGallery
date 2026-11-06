import Foundation

struct MediaPage: Decodable, Sendable {
    let items: [MobileMediaSummary]
    let total: Int
    let limit: Int
    let offset: Int
    var characterLora: String? = nil

    enum CodingKeys: String, CodingKey {
        case items, total, limit, offset
        case characterLora = "character_lora"
    }
}
