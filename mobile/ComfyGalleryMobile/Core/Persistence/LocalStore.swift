import Foundation
import SwiftData
import OSLog

@MainActor
final class LocalStore {
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "LocalStore")
    let modelContainer: ModelContainer
    let modelContext: ModelContext

    init() {
        let schema = Schema([PendingMutation.self, ServerProfile.self, CachedSessionSummary.self])
        let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        do {
            self.modelContainer = try ModelContainer(for: schema, configurations: [config])
            self.modelContext = modelContainer.mainContext
        } catch {
            fatalError("Failed to create ModelContainer: \(error)")
        }
    }

    func activeProfile() throws -> ServerProfile? {
        var descriptor = FetchDescriptor<ServerProfile>(
            predicate: #Predicate { $0.isActive == true }
        )
        descriptor.fetchLimit = 1
        return try modelContext.fetch(descriptor).first
    }

    func saveProfile(_ profile: ServerProfile) throws {
        modelContext.insert(profile)
        try modelContext.save()
    }

    func pendingMutations(for evaluationUUID: String) throws -> [PendingMutation] {
        var descriptor = FetchDescriptor<PendingMutation>(
            predicate: #Predicate { $0.evaluationUUID == evaluationUUID },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        return try modelContext.fetch(descriptor)
    }

    func allPendingMutations() throws -> [PendingMutation] {
        let descriptor = FetchDescriptor<PendingMutation>(
            sortBy: [SortDescriptor(\.createdAt)]
        )
        return try modelContext.fetch(descriptor)
    }

    func insertPendingMutation(_ mutation: PendingMutation) throws {
        modelContext.insert(mutation)
        try modelContext.save()
    }

    func deletePendingMutation(_ mutation: PendingMutation) throws {
        modelContext.delete(mutation)
        try modelContext.save()
    }

    func clearAll() throws {
        try modelContext.delete(model: PendingMutation.self)
        try modelContext.delete(model: ServerProfile.self)
        try modelContext.delete(model: CachedSessionSummary.self)
        try modelContext.save()
    }

    func saveContext() throws {
        try modelContext.save()
    }

    func clearPendingMutations(for profileUUID: String) throws {
        let mutations = try modelContext.fetch(
            FetchDescriptor<PendingMutation>(
                predicate: #Predicate { $0.serverProfileUUID == profileUUID }
            )
        )
        for mutation in mutations {
            modelContext.delete(mutation)
        }
        try modelContext.save()
    }
}
