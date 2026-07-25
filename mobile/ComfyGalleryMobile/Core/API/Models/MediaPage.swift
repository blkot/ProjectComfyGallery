import Foundation

struct MediaPage: Decodable, Sendable {
    let items: [MobileMediaSummary]
    let total: Int
    let limit: Int
    let offset: Int
}

struct MobileMediaSummary: Decodable, Identifiable, Sendable {
    let id: String
    let kind: MediaKind
    let evaluationState: EvaluationState?
    let isTrash: Bool?
    let previewURL: String

    enum CodingKeys: String, CodingKey {
        case id, kind
        case evaluationState = "evaluation_state"
        case isTrash = "is_trash"
        case previewURL = "preview_url"
    }
}
