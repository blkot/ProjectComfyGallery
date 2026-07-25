import Foundation

struct ReviewSummary: Decodable, Sendable {
    let notStartedCount: Int
    let inProgressCount: Int
    let completeCount: Int
    let trashCount: Int
    let activeSessionCount: Int

    enum CodingKeys: String, CodingKey {
        case notStartedCount = "not_started_count"
        case inProgressCount = "in_progress_count"
        case completeCount = "complete_count"
        case trashCount = "trash_count"
        case activeSessionCount = "active_session_count"
    }
}
