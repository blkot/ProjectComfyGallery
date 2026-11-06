import Foundation

struct CharacterLoraOption: Decodable, Identifiable, Sendable {
    let name: String
    let mediaCount: Int
    var id: String { name }
    enum CodingKeys: String, CodingKey { case name, mediaCount = "media_count" }
}
