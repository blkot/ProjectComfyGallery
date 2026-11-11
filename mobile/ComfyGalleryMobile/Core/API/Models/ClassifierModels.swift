import Foundation

enum ClassifierRating: String, CaseIterable, Codable, Sendable {
    case safe
    case sexy
    case nudity
    case explicit
    case review

    var title: String {
        switch self {
        case .safe: "Safe"
        case .sexy: "Sexy"
        case .nudity: "Nudity"
        case .explicit: "Explicit"
        case .review: "待复核"
        }
    }

    var symbol: String {
        switch self {
        case .safe: "checkmark.shield.fill"
        case .sexy: "eye.fill"
        case .nudity: "exclamationmark.shield.fill"
        case .explicit: "hand.raised.fill"
        case .review: "questionmark.circle.fill"
        }
    }

    var isHumanRating: Bool { self != .review }
}

enum ClassifierStatus: String, CaseIterable, Codable, Sendable {
    case unclassified
    case suggested
    case needsReview = "needs_review"
    case reviewed
    case processing
    case failed

    var title: String {
        switch self {
        case .unclassified: "未分类"
        case .suggested: "AI 已建议"
        case .needsReview: "待复核"
        case .reviewed: "人工已确认"
        case .processing: "处理中"
        case .failed: "分析失败"
        }
    }

    var symbol: String {
        switch self {
        case .unclassified: "circle.dashed"
        case .suggested: "sparkles"
        case .needsReview: "questionmark.circle"
        case .reviewed: "person.crop.circle.badge.checkmark"
        case .processing: "hourglass"
        case .failed: "exclamationmark.triangle"
        }
    }
}

struct MediaSafetyAssessmentSummary: Decodable, Equatable, Sendable {
    let status: String
    let label: String?
    let suggestedRating: ClassifierRating?
    let confidence: Double?
    let needsReview: Bool

    enum CodingKeys: String, CodingKey {
        case status, label, confidence
        case suggestedRating = "suggested_rating"
        case needsReview = "needs_review"
    }
}

struct MediaSafetyReviewSummary: Decodable, Equatable, Sendable {
    let rating: ClassifierRating
    let reviewedAt: String

    enum CodingKeys: String, CodingKey {
        case rating
        case reviewedAt = "reviewed_at"
    }
}

struct ClassifierDetection: Decodable, Sendable, Identifiable {
    let detectionClass: String
    let score: Double
    let box: [Double]

    var id: String { "\(detectionClass)-\(box.map { String($0) }.joined(separator: ","))" }

    enum CodingKeys: String, CodingKey {
        case score, box
        case detectionClass = "class"
    }
}

struct ClassifierAssessment: Decodable, Sendable {
    let status: String
    let label: String?
    let suggestedRating: ClassifierRating?
    let confidence: Double?
    let margin: Double?
    let scores: [String: Double]
    let needsReview: Bool
    let modelID: String
    let modelRevision: String
    let inferenceBackend: String
    let nudityDetectorStatus: String
    let nudityDetectorMode: String
    let nudityDetected: Bool
    let nudityModelID: String?
    let nudityModelRevision: String?
    let nudityDetections: [ClassifierDetection]
    let errorMessage: String?
    let completedAt: String?

    enum CodingKeys: String, CodingKey {
        case status, label, confidence, margin, scores
        case suggestedRating = "suggested_rating"
        case needsReview = "needs_review"
        case modelID = "model_id"
        case modelRevision = "model_revision"
        case inferenceBackend = "inference_backend"
        case nudityDetectorStatus = "nudity_detector_status"
        case nudityDetectorMode = "nudity_detector_mode"
        case nudityDetected = "nudity_detected"
        case nudityModelID = "nudity_model_id"
        case nudityModelRevision = "nudity_model_revision"
        case nudityDetections = "nudity_detections"
        case errorMessage = "error_message"
        case completedAt = "completed_at"
    }
}

struct ClassifierReview: Decodable, Sendable {
    let rating: ClassifierRating
    let reviewerUserID: String
    let reviewedAt: String

    enum CodingKeys: String, CodingKey {
        case rating
        case reviewerUserID = "reviewer_user_id"
        case reviewedAt = "reviewed_at"
    }
}

struct ClassifierJobSummary: Decodable, Sendable {
    let status: String
}

struct ClassifierStatusResponse: Decodable, Sendable {
    let mediaID: String
    let assessment: ClassifierAssessment?
    let review: ClassifierReview?
    let job: ClassifierJobSummary?

    enum CodingKeys: String, CodingKey {
        case assessment, review, job
        case mediaID = "media_id"
    }
}

struct ClassifierBatchResponse: Decodable, Sendable {
    let requestedCount: Int
    let queuedCount: Int
    let reusedCount: Int
    let skippedCount: Int
    let queueFailedCount: Int
    let jobIDs: [String]

    enum CodingKeys: String, CodingKey {
        case requestedCount = "requested_count"
        case queuedCount = "queued_count"
        case reusedCount = "reused_count"
        case skippedCount = "skipped_count"
        case queueFailedCount = "queue_failed_count"
        case jobIDs = "job_ids"
    }
}

struct ClassifierQueueSnapshot: Decodable, Sendable {
    let ids: [String]
    let total: Int
    let truncated: Bool
}

struct ClassifierReviewQueue: Codable, Identifiable, Sendable {
    let id: String
    let mediaIDs: [String]
    let total: Int
    let truncated: Bool
    var position: Int

    init(snapshot: ClassifierQueueSnapshot, position: Int = 0) {
        id = UUID().uuidString
        var seen = Set<String>()
        mediaIDs = snapshot.ids.filter { seen.insert($0).inserted }
        total = snapshot.total
        truncated = snapshot.truncated
        self.position = min(max(0, position), max(0, mediaIDs.count - 1))
    }

    var currentID: String? { mediaIDs.indices.contains(position) ? mediaIDs[position] : nil }
    var previousID: String? { mediaIDs.indices.contains(position - 1) ? mediaIDs[position - 1] : nil }
    var nextID: String? { mediaIDs.indices.contains(position + 1) ? mediaIDs[position + 1] : nil }
}

enum ClassifierProjection {
    static func effectiveRating(assessment: MediaSafetyAssessmentSummary?, review: MediaSafetyReviewSummary?) -> ClassifierRating? {
        review?.rating ?? (assessment?.status == "completed" ? assessment?.suggestedRating : nil)
    }

    static func status(assessment: MediaSafetyAssessmentSummary?, review: MediaSafetyReviewSummary?) -> ClassifierStatus {
        if review != nil { return .reviewed }
        guard let assessment else { return .unclassified }
        switch assessment.status {
        case "queued", "running": return .processing
        case "failed": return .failed
        case "completed": return assessment.needsReview ? .needsReview : .suggested
        default: return .unclassified
        }
    }

    static func matches(status filter: ClassifierStatus?, rating ratingFilter: ClassifierRating?, assessment: MediaSafetyAssessmentSummary?, review: MediaSafetyReviewSummary?) -> Bool {
        if let filter, status(assessment: assessment, review: review) != filter { return false }
        if let ratingFilter, effectiveRating(assessment: assessment, review: review) != ratingFilter { return false }
        return true
    }
}
