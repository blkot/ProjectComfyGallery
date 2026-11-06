import Foundation

struct PromptRegistryLookup: Decodable, Sendable {
    let promptID: String
    let source: String
    let index: String
    let entry: Entry?
    let media: [MobileMediaSummary]
    let totalMedia: Int
    let limit: Int
    let offset: Int

    struct Entry: Decodable, Sendable {
        let prompt: String
        let negativePrompt: String?
        enum CodingKeys: String, CodingKey { case prompt, negativePrompt = "negative_prompt" }
    }
    enum CodingKeys: String, CodingKey {
        case source, index, entry, media, limit, offset
        case promptID = "prompt_id", totalMedia = "total_media"
    }
}
