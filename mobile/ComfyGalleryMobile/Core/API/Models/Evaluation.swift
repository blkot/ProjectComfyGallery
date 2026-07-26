import Foundation

struct Evaluation: Decodable, Identifiable, Sendable {
    let id: String
    let evaluationKind: String
    let progressState: ProgressState
    let isTrash: Bool
    let version: Int
    let criteria: [Criterion]
    let scores: [EvaluationScore]

    enum CodingKeys: String, CodingKey {
        case id, version, criteria, scores
        case evaluationKind = "evaluation_kind"
        case progressState = "progress_state"
        case isTrash = "is_trash"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        evaluationKind = try c.decodeIfPresent(String.self, forKey: .evaluationKind) ?? "base"
        progressState = (try? c.decodeIfPresent(ProgressState.self, forKey: .progressState)) ?? .notStarted
        isTrash = try c.decodeIfPresent(Bool.self, forKey: .isTrash) ?? false
        version = try c.decodeIfPresent(Int.self, forKey: .version) ?? 0
        criteria = try c.decodeIfPresent([Criterion].self, forKey: .criteria) ?? []
        scores = try c.decodeIfPresent([EvaluationScore].self, forKey: .scores) ?? []
    }
}

struct Criterion: Decodable, Identifiable, Sendable {
    let id: String
    let label: String
    let description: String?
    let minValue: Int?
    let maxValue: Int?

    enum CodingKeys: String, CodingKey {
        case id, label, description
        case minValue = "min_value"
        case maxValue = "max_value"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? ""
        label = try c.decodeIfPresent(String.self, forKey: .label) ?? "Criterion"
        description = try c.decodeIfPresent(String.self, forKey: .description)
        minValue = try c.decodeIfPresent(Int.self, forKey: .minValue)
        maxValue = try c.decodeIfPresent(Int.self, forKey: .maxValue)
    }
}

struct EvaluationScore: Decodable, Sendable {
    let criterionVersionId: String
    let state: ScoreState
    let value: Int?
    let naReason: String?

    enum CodingKeys: String, CodingKey {
        case state, value
        case criterionVersionId = "criterion_version_id"
        case naReason = "na_reason"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        criterionVersionId = try c.decodeIfPresent(String.self, forKey: .criterionVersionId) ?? ""
        state = (try? c.decodeIfPresent(ScoreState.self, forKey: .state)) ?? .unset
        value = try c.decodeIfPresent(Int.self, forKey: .value)
        naReason = try c.decodeIfPresent(String.self, forKey: .naReason)
    }
}

struct SetScoreRequest: Encodable, Sendable {
    let expectedVersion: Int
    let state: ScoreState
    let value: Int?
    let naReason: String?

    enum CodingKeys: String, CodingKey {
        case state, value
        case expectedVersion = "expected_version"
        case naReason = "na_reason"
    }
}

struct DeleteScoreRequest: Encodable, Sendable {
    let expectedVersion: Int

    enum CodingKeys: String, CodingKey {
        case expectedVersion = "expected_version"
    }
}

struct TrashRestoreRequest: Encodable, Sendable {
    let expectedVersion: Int

    enum CodingKeys: String, CodingKey {
        case expectedVersion = "expected_version"
    }
}
