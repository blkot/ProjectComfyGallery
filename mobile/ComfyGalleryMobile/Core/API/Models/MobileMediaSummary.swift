import Foundation

/// Deliberately excludes workflow/model metadata from the browsing surface.
struct MobileMediaSummary: Decodable, Identifiable, Sendable {
    let id: String
    let kind: MediaKind
    let evaluationState: EvaluationState?
    let isTrash: Bool?
    let previewURL: String
    let favorite: Bool?
    let width: Int?
    let height: Int?
    let durationSeconds: Double?
    let fileCreatedAt: String?
    let createdAt: String?
    var contentRating: String? = nil
    var characterLora: String? = nil
    var mediaSafetyAssessment: MediaSafetyAssessmentSummary? = nil
    var mediaSafetyReview: MediaSafetyReviewSummary? = nil
    var originalFilename: String? = nil
    var byteSize: Int64? = nil

    var durationLabel: String? {
        guard let durationSeconds, durationSeconds.isFinite, durationSeconds >= 0,
              durationSeconds < Double(Int.max) else { return nil }
        let seconds = Int(durationSeconds)
        if seconds >= 3600 { return String(format: "%d:%02d:%02d", seconds / 3600, (seconds / 60) % 60, seconds % 60) }
        return String(format: "%d:%02d", seconds / 60, seconds % 60)
    }

    var fileDate: Date? {
        guard let fileCreatedAt else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: fileCreatedAt) ?? ISO8601DateFormatter().date(from: fileCreatedAt)
    }

    enum CodingKeys: String, CodingKey {
        case id, kind, favorite, width, height
        case evaluationState = "evaluation_state", isTrash = "is_trash"
        case previewURL = "preview_url", durationSeconds = "duration_seconds"
        case fileCreatedAt = "file_created_at", createdAt = "created_at"
        case contentRating = "content_rating", characterLora = "character_lora"
        case mediaSafetyAssessment = "media_safety_assessment"
        case mediaSafetyReview = "media_safety_review"
        case originalFilename = "original_filename", byteSize = "byte_size"
    }
}
