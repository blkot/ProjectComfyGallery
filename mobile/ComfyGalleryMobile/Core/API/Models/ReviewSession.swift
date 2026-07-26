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
    let optionalModules: [String]?
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

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        name = try c.decodeIfPresent(String.self, forKey: .name)
        sourceKind = (try? c.decodeIfPresent(SourceKind.self, forKey: .sourceKind)) ?? .random
        orderingMode = (try? c.decodeIfPresent(OrderingMode.self, forKey: .orderingMode)) ?? .random
        status = (try? c.decodeIfPresent(SessionStatus.self, forKey: .status)) ?? .active
        currentCursor = try c.decodeIfPresent(Int.self, forKey: .currentCursor)
        candidateCount = try c.decodeIfPresent(Int.self, forKey: .candidateCount) ?? 0
        progressCounts = try c.decodeIfPresent(ProgressCounts.self, forKey: .progressCounts)
        optionalModules = try c.decodeIfPresent([String].self, forKey: .optionalModules) ?? []
        lastOpenedAt = try c.decodeIfPresent(String.self, forKey: .lastOpenedAt)
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

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        notStarted = try c.decodeIfPresent(Int.self, forKey: .notStarted) ?? 0
        inProgress = try c.decodeIfPresent(Int.self, forKey: .inProgress) ?? 0
        complete = try c.decodeIfPresent(Int.self, forKey: .complete) ?? 0
        trash = try c.decodeIfPresent(Int.self, forKey: .trash) ?? 0
    }

    init(notStarted: Int, inProgress: Int, complete: Int, trash: Int) {
        self.notStarted = notStarted
        self.inProgress = inProgress
        self.complete = complete
        self.trash = trash
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

    init(kind: MediaKind? = nil, evaluationState: EvaluationState? = nil, trash: Bool? = nil) {
        self.kind = kind
        self.evaluationState = evaluationState
        self.trash = trash
    }

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

