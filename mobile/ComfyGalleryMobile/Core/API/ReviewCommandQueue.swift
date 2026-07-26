import Foundation
import OSLog

@MainActor
final class ReviewCommandQueue {
    private let apiClient: APIClient
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "CommandQueue")
    private var laneStates: [String: LaneState] = [:]
    private var latestVersions: [String: Int] = [:]
    private var isShutdown = false

    private final class LaneState {
        var isProcessing = false
        var waiters: [CheckedContinuation<Void, Never>] = []
    }

    init(apiClient: APIClient, localStore: LocalStore) {
        self.apiClient = apiClient
        self.localStore = localStore
    }

    func enqueue(_ mutation: PendingMutation) async throws -> Evaluation {
        guard !isShutdown else {
            throw APIError.invalidResponse
        }

        let key = mutation.evaluationUUID
        let lane = laneStates[key] ?? LaneState()
        laneStates[key] = lane

        while lane.isProcessing {
            await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
                lane.waiters.append(cont)
            }
        }

        lane.isProcessing = true
        defer {
            lane.isProcessing = false
            let waiters = lane.waiters
            lane.waiters = []
            for w in waiters { w.resume() }
        }

        var effective = mutation
        if let lv = latestVersions[key], lv > effective.baseEvaluationVersion {
            logger.log("Bumping expected_version \(mutation.baseEvaluationVersion) -> \(lv) for \(mutation.commandKind.rawValue, privacy: .public)")
            effective.baseEvaluationVersion = lv
        }

        do {
            let evaluation = try await execute(effective)
            latestVersions[key] = evaluation.version
            return evaluation
        } catch let error as APIError {
            if case .conflict = error {
                latestVersions[key] = nil
            }
            throw error
        }
    }

    func shutdown() {
        isShutdown = true
    }

    func laneIsIdle(for evaluationUUID: String) -> Bool {
        laneStates[evaluationUUID]?.isProcessing != true
    }

    func noteExternalVersion(_ version: Int, for evaluationUUID: String) {
        let current = latestVersions[evaluationUUID] ?? 0
        if version > current {
            latestVersions[evaluationUUID] = version
        }
    }

    private func execute(_ mutation: PendingMutation) async throws -> Evaluation {
        let endpoint: Endpoint
        switch mutation.commandKind {
        case .score:
            let request = SetScoreRequest(
                expectedVersion: mutation.baseEvaluationVersion,
                state: .scored,
                value: mutation.intendedValue,
                naReason: nil
            )
            endpoint = .setScore(
                evaluationID: mutation.evaluationUUID,
                criterionVersionID: mutation.criterionVersionUUID ?? "",
                request
            )
        case .na:
            let request = SetScoreRequest(
                expectedVersion: mutation.baseEvaluationVersion,
                state: .na,
                value: nil,
                naReason: nil
            )
            endpoint = .setScore(
                evaluationID: mutation.evaluationUUID,
                criterionVersionID: mutation.criterionVersionUUID ?? "",
                request
            )
        case .clear:
            let request = DeleteScoreRequest(expectedVersion: mutation.baseEvaluationVersion)
            endpoint = .deleteScore(
                evaluationID: mutation.evaluationUUID,
                criterionVersionID: mutation.criterionVersionUUID ?? "",
                request
            )
        case .trash:
            let request = TrashRestoreRequest(expectedVersion: mutation.baseEvaluationVersion)
            endpoint = .trash(evaluationID: mutation.evaluationUUID, request)
        case .restore:
            let request = TrashRestoreRequest(expectedVersion: mutation.baseEvaluationVersion)
            endpoint = .restore(evaluationID: mutation.evaluationUUID, request)
        }
        return try await apiClient.request(endpoint)
    }
}
