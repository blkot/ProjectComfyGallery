import Foundation

struct ReviewSession: Decodable, Identifiable, Sendable {
    let id: String
    let name: String?
    let sourceKind: SourceKind
    let orderingMode: OrderingMode
    let status: SessionStatus
    let currentCursor: Int?
    let candidateCount: Int
    let progressCounts: ProgressCounts?
    let optionalModules: [String]
    let lastOpenedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, name, status
        case sourceKind = "source_kind"
        case orderingMode = "ordering_mode"
        case currentCursor = "current_cursor"
        case candidateCount = "candidate_count"
        case progressCounts = "progress_counts"
        case optionalModules = "optional_modules"
        case lastOpenedAt = "last_opened_at"
    }
}

struct ProgressCounts: Decodable, Sendable {
    let notStarted: Int
    let inProgress: Int
    let complete: Int
    let trash: Int

    enum CodingKeys: String, CodingKey {
        case notStarted = "not_started"
        case inProgress = "in_progress"
        case complete, trash
    }
}

struct CreateSessionRequest: Encodable, Sendable {
    let name: String?
    let sourceKind: SourceKind
    let filter: MediaFilter?
    let randomLimit: Int
    let orderingMode: OrderingMode
    let optionalModules: [String]

    enum CodingKeys: String, CodingKey {
        case name, filter
        case sourceKind = "source_kind"
        case randomLimit = "random_limit"
        case orderingMode = "ordering_mode"
        case optionalModules = "optional_modules"
    }
}

struct MediaFilter: Encodable, Sendable {
    let kind: MediaKind?
    let evaluationState: EvaluationState?
    let trash: Bool?

    enum CodingKeys: String, CodingKey {
        case kind
        case evaluationState = "evaluation_state"
        case trash
    }
}

struct PatchSessionBody: Encodable, Sendable {
    let currentCursor: Int?
    let status: SessionStatus?

    enum CodingKeys: String, CodingKey {
        case currentCursor = "current_cursor"
        case status
    }
}
