import Foundation
import OSLog

actor ReviewCommandQueue {
    private let apiClient: APIClient
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "CommandQueue")
    private var lanes: [String: Lane] = [:]
    private let maxRetries = 5
    private let baseBackoff: UInt64 = 500_000_000 // 500ms
    private var isShutdown = false

    struct Lane {
        var commands: [PendingMutation] = []
        var isProcessing = false
    }

    init(apiClient: APIClient, localStore: LocalStore) {
        self.apiClient = apiClient
        self.localStore = localStore
    }

    func enqueue(_ mutation: PendingMutation) async {
        guard !isShutdown else { return }
        if lanes[mutation.evaluationUUID] == nil {
            lanes[mutation.evaluationUUID] = Lane()
        }
        if let existing = lanes[mutation.evaluationUUID]?.commands.last,
           existing.commandKind == mutation.commandKind,
           existing.criterionVersionUUID == mutation.criterionVersionUUID {
            // Coalesce unsent same-criterion changes
            existing.intendedValue = mutation.intendedValue
            existing.baseEvaluationVersion = mutation.baseEvaluationVersion
            return
        }
        lanes[mutation.evaluationUUID]?.commands.append(mutation)
        await processLane(evaluationUUID: mutation.evaluationUUID)
    }

    func shutdown() {
        isShutdown = true
    }

    func reconcilePending(for evaluationUUID: String) async -> Bool {
        return lanes[evaluationUUID]?.commands.isEmpty ?? true
    }

    private func processLane(evaluationUUID: String) async {
        guard var lane = lanes[evaluationUUID], !lane.isProcessing else { return }
        lane.isProcessing = true
        lanes[evaluationUUID] = lane

        defer {
            lanes[evaluationUUID]?.isProcessing = false
        }

        while let command = lanes[evaluationUUID]?.commands.first {
            guard !isShutdown else { break }
            do {
                try await execute(command)
                lanes[evaluationUUID]?.commands.removeFirst()
                try? await localStore.deletePendingMutation(command)
            } catch let error as APIError {
                await handleError(error, mutation: command)
                if !error.isRetryable { break }
                if command.attemptCount >= maxRetries { break }
                let backoff = baseBackoff * UInt64(pow(2.0, Double(min(command.attemptCount, 10) - 1)))
                let jitter = UInt64.random(in: 0...(backoff / 4))
                try? await Task.sleep(nanoseconds: backoff + jitter)
                continue
            } catch {
                command.lastErrorCategory = "unknown"
                command.attemptCount += 1
                try? await localStore.modelContext.save()
                if command.attemptCount >= maxRetries { break }
                let backoff = baseBackoff
                let jitter = UInt64.random(in: 0...(backoff / 4))
                try? await Task.sleep(nanoseconds: backoff + jitter)
            }
        }
    }

    private func execute(_ mutation: PendingMutation) async throws {
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
        let _: Evaluation = try await apiClient.request(endpoint)
    }

    private func handleError(_ error: APIError, mutation: PendingMutation) async {
        mutation.attemptCount += 1
        mutation.lastErrorCategory = String(describing: error)
        try? await localStore.modelContext.save()

        if error.requiresReauthentication {
            isShutdown = true
            lanes.removeAll()
        }
    }
}
