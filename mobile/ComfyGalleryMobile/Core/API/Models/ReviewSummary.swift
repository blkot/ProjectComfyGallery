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

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        notStartedCount = try c.decodeIfPresent(Int.self, forKey: .notStartedCount) ?? 0
        inProgressCount = try c.decodeIfPresent(Int.self, forKey: .inProgressCount) ?? 0
        completeCount = try c.decodeIfPresent(Int.self, forKey: .completeCount) ?? 0
        trashCount = try c.decodeIfPresent(Int.self, forKey: .trashCount) ?? 0
        activeSessionCount = try c.decodeIfPresent(Int.self, forKey: .activeSessionCount) ?? 0
    }
}

