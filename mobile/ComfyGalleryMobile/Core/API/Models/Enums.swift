import Foundation

protocol TolerantEnum: RawRepresentable, Codable, Sendable where RawValue == String {
    static var allKnownCases: [Self] { get }
    static var unknownFallback: Self { get }
}

extension TolerantEnum {
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let raw = try container.decode(String.self)
        if let value = Self(rawValue: raw) {
            self = value
        } else {
            self = Self.unknownFallback
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }
}

enum MediaKind: String, TolerantEnum {
    case image, video

    static var allKnownCases: [MediaKind] { [.image, .video] }
    static var unknownFallback: MediaKind { .image }
}

enum EvaluationState: String, TolerantEnum {
    case notStarted = "not_started"
    case inProgress = "in_progress"
    case complete

    static var allKnownCases: [EvaluationState] { [.notStarted, .inProgress, .complete] }
    static var unknownFallback: EvaluationState { .notStarted }
}

enum ProgressState: String, TolerantEnum {
    case notStarted = "not_started"
    case inProgress = "in_progress"
    case complete

    static var allKnownCases: [ProgressState] { [.notStarted, .inProgress, .complete] }
    static var unknownFallback: ProgressState { .notStarted }
}

enum SessionStatus: String, TolerantEnum {
    case active, finished, abandoned

    static var allKnownCases: [SessionStatus] { [.active, .finished, .abandoned] }
    static var unknownFallback: SessionStatus { .active }
}

enum SourceKind: String, TolerantEnum {
    case random
    case inProgress = "in_progress"
    case filter

    static var allKnownCases: [SourceKind] { [.random, .inProgress, .filter] }
    static var unknownFallback: SourceKind { .random }
}

enum OrderingMode: String, TolerantEnum {
    case random, stable

    static var allKnownCases: [OrderingMode] { [.random, .stable] }
    static var unknownFallback: OrderingMode { .random }
}

enum ScoreState: String, TolerantEnum {
    case unset, scored, na

    static var allKnownCases: [ScoreState] { [.unset, .scored, .na] }
    static var unknownFallback: ScoreState { .unset }
}

enum CommandKind: String, Codable, Sendable {
    case score, na, clear, trash, restore
}
