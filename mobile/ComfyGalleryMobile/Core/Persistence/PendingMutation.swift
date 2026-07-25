import Foundation
import SwiftData

@Model
final class PendingMutation {
    var localUUID: String
    var serverProfileUUID: String
    var reviewSessionUUID: String
    var mediaUUID: String
    var evaluationUUID: String
    var criterionVersionUUID: String?
    var commandKindRaw: String
    var intendedValue: Int?
    var intendedState: String?
    var baseEvaluationVersion: Int
    var createdAt: Date
    var attemptCount: Int
    var lastErrorCategory: String?

    var commandKind: CommandKind {
        CommandKind(rawValue: commandKindRaw) ?? .score
    }

    init(
        localUUID: String = UUID().uuidString,
        serverProfileUUID: String,
        reviewSessionUUID: String,
        mediaUUID: String,
        evaluationUUID: String,
        criterionVersionUUID: String? = nil,
        commandKind: CommandKind,
        intendedValue: Int? = nil,
        intendedState: String? = nil,
        baseEvaluationVersion: Int,
        createdAt: Date = Date(),
        attemptCount: Int = 0,
        lastErrorCategory: String? = nil
    ) {
        self.localUUID = localUUID
        self.serverProfileUUID = serverProfileUUID
        self.reviewSessionUUID = reviewSessionUUID
        self.mediaUUID = mediaUUID
        self.evaluationUUID = evaluationUUID
        self.criterionVersionUUID = criterionVersionUUID
        self.commandKindRaw = commandKind.rawValue
        self.intendedValue = intendedValue
        self.intendedState = intendedState
        self.baseEvaluationVersion = baseEvaluationVersion
        self.createdAt = createdAt
        self.attemptCount = attemptCount
        self.lastErrorCategory = lastErrorCategory
    }
}

@Model
final class ServerProfile {
    var uuid: String
    var baseURL: String
    var displayName: String?
    var lastServerVersion: String?
    var lastConnectionDate: Date?
    var isActive: Bool

    init(
        uuid: String = UUID().uuidString,
        baseURL: String,
        displayName: String? = nil,
        lastServerVersion: String? = nil,
        lastConnectionDate: Date? = nil,
        isActive: Bool = true
    ) {
        self.uuid = uuid
        self.baseURL = baseURL
        self.displayName = displayName
        self.lastServerVersion = lastServerVersion
        self.lastConnectionDate = lastConnectionDate
        self.isActive = isActive
    }
}

@Model
final class CachedSessionSummary {
    var sessionUUID: String
    var name: String?
    var status: String
    var currentCursor: Int
    var candidateCount: Int
    var lastOpenedAt: Date?
    var sourceKind: String
    var serverProfileUUID: String

    init(
        sessionUUID: String,
        name: String? = nil,
        status: String,
        currentCursor: Int = 0,
        candidateCount: Int = 0,
        lastOpenedAt: Date? = nil,
        sourceKind: String,
        serverProfileUUID: String
    ) {
        self.sessionUUID = sessionUUID
        self.name = name
        self.status = status
        self.currentCursor = currentCursor
        self.candidateCount = candidateCount
        self.lastOpenedAt = lastOpenedAt
        self.sourceKind = sourceKind
        self.serverProfileUUID = serverProfileUUID
    }
}
