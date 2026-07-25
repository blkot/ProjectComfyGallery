import Foundation

struct ReviewItem: Decodable, Sendable {
    let session: ReviewItemSession
    let position: Int
    let media: ReviewMedia
    let prompts: [ReviewPrompt]
    let evaluations: [Evaluation]
}

struct ReviewItemSession: Decodable, Sendable {
    let id: String
    let currentCursor: Int?
    let candidateCount: Int
    let progressCounts: ProgressCounts?

    enum CodingKeys: String, CodingKey {
        case id
        case currentCursor = "current_cursor"
        case candidateCount = "candidate_count"
        case progressCounts = "progress_counts"
    }
}

struct ReviewMedia: Decodable, Sendable {
    let id: String
    let kind: MediaKind
    let previewURL: String
    let playbackURL: String?
    let width: Int?
    let height: Int?
    let durationSeconds: Double?

    enum CodingKeys: String, CodingKey {
        case id, kind, width, height
        case previewURL = "preview_url"
        case playbackURL = "playback_url"
        case durationSeconds = "duration_seconds"
    }
}

struct ReviewPrompt: Decodable, Identifiable, Sendable {
    let role: String
    let label: String
    let text: String

    var id: String { "\(role)-\(label)" }
}
