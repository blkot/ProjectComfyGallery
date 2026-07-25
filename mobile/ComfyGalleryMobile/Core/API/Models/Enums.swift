import Foundation

enum MediaKind: String, Decodable, Sendable {
    case image, video
}

enum EvaluationState: String, Decodable, Sendable {
    case notStarted = "not_started"
    case inProgress = "in_progress"
    case complete
}

enum ProgressState: String, Decodable, Sendable {
    case notStarted = "not_started"
    case inProgress = "in_progress"
    case complete
}

enum SessionStatus: String, Codable, Sendable {
    case active, finished, abandoned
}

enum SourceKind: String, Codable, Sendable {
    case random
    case inProgress = "in_progress"
    case filter
}

enum OrderingMode: String, Codable, Sendable {
    case random, stable
}

enum ScoreState: String, Codable, Sendable {
    case unset, scored, na
}

enum CommandKind: String, Codable, Sendable {
    case score, na, clear, trash, restore
}
