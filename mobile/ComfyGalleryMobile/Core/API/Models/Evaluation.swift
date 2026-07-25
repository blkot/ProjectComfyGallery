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
