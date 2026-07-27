import Foundation
import SwiftData

@Model
final class StoredServerProfile {
    @Attribute(.unique) var identifier: UUID
    var baseURL: String
    var createdAt: Date

    init(identifier: UUID, baseURL: String, createdAt: Date) {
        self.identifier = identifier
        self.baseURL = baseURL
        self.createdAt = createdAt
    }
}

@Model
final class StoredLibraryState {
    @Attribute(.unique) var identifier: String
    var kindRawValue: String
    var preferenceFilterRawValue: String = GalleryPreferenceFilter.all.rawValue
    var includesTrash: Bool
    var sortRawValue: String
    var scrollAnchor: UUID?
    var selectedMediaID: UUID?

    init(
        identifier: String = "primary",
        kindRawValue: String = GalleryKindFilter.all.rawValue,
        preferenceFilterRawValue: String = GalleryPreferenceFilter.all.rawValue,
        includesTrash: Bool = false,
        sortRawValue: String = MediaSort.newest.rawValue,
        scrollAnchor: UUID? = nil,
        selectedMediaID: UUID? = nil
    ) {
        self.identifier = identifier
        self.kindRawValue = kindRawValue
        self.preferenceFilterRawValue = preferenceFilterRawValue
        self.includesTrash = includesTrash
        self.sortRawValue = sortRawValue
        self.scrollAnchor = scrollAnchor
        self.selectedMediaID = selectedMediaID
    }
}

@Model
final class CachedResourceRecord {
    @Attribute(.unique) var key: String
    var relativePath: String
    var byteCount: Int64
    var lastAccessedAt: Date

    init(key: String, relativePath: String, byteCount: Int64, lastAccessedAt: Date = .now) {
        self.key = key
        self.relativePath = relativePath
        self.byteCount = byteCount
        self.lastAccessedAt = lastAccessedAt
    }
}

enum PersistenceFactory {
    static func makeContainer(inMemory: Bool = false) throws -> ModelContainer {
        let schema = Schema([
            StoredServerProfile.self,
            StoredLibraryState.self,
            CachedResourceRecord.self
        ])
        let configuration = ModelConfiguration(
            "ComfyGalleryXR",
            schema: schema,
            isStoredInMemoryOnly: inMemory
        )
        return try ModelContainer(for: schema, configurations: [configuration])
    }
}

@MainActor
final class PersistenceStore {
    let container: ModelContainer
    private let context: ModelContext

    init(container: ModelContainer) {
        self.container = container
        context = ModelContext(container)
        context.autosaveEnabled = true
    }

    func loadProfile() -> ServerProfile? {
        var descriptor = FetchDescriptor<StoredServerProfile>()
        descriptor.fetchLimit = 1
        guard
            let stored = try? context.fetch(descriptor).first,
            let url = URL(string: stored.baseURL)
        else {
            return nil
        }
        return ServerProfile(id: stored.identifier, baseURL: url, createdAt: stored.createdAt)
    }

    func saveProfile(_ profile: ServerProfile) throws {
        for existing in try context.fetch(FetchDescriptor<StoredServerProfile>()) {
            context.delete(existing)
        }
        context.insert(
            StoredServerProfile(
                identifier: profile.id,
                baseURL: profile.baseURL.absoluteString,
                createdAt: profile.createdAt
            )
        )
        try context.save()
    }

    func clearProfile() throws {
        for profile in try context.fetch(FetchDescriptor<StoredServerProfile>()) {
            context.delete(profile)
        }
        try context.save()
    }

    func loadLibraryState() -> (GalleryScope, UUID?, UUID?) {
        var descriptor = FetchDescriptor<StoredLibraryState>()
        descriptor.fetchLimit = 1
        guard let stored = try? context.fetch(descriptor).first else {
            return (GalleryScope(), nil, nil)
        }
        let kind = GalleryKindFilter(rawValue: stored.kindRawValue) ?? .all
        let preference = GalleryPreferenceFilter(
            rawValue: stored.preferenceFilterRawValue
        ) ?? .all
        let sort = MediaSort(rawValue: stored.sortRawValue) ?? .newest
        return (
            GalleryScope(
                kind: kind,
                preference: preference,
                includesTrash: stored.includesTrash,
                sort: sort
            ),
            stored.scrollAnchor,
            stored.selectedMediaID
        )
    }

    func saveLibraryState(
        scope: GalleryScope,
        scrollAnchor: UUID?,
        selectedMediaID: UUID?
    ) {
        let descriptor = FetchDescriptor<StoredLibraryState>()
        let stored = (try? context.fetch(descriptor).first) ?? StoredLibraryState()
        if stored.modelContext == nil {
            context.insert(stored)
        }
        stored.kindRawValue = scope.kind.rawValue
        stored.preferenceFilterRawValue = scope.preference.rawValue
        stored.includesTrash = scope.includesTrash
        stored.sortRawValue = scope.sort.rawValue
        stored.scrollAnchor = scrollAnchor
        stored.selectedMediaID = selectedMediaID
        try? context.save()
    }
}

@ModelActor
actor CacheIndexStore {
    struct Record: Sendable {
        let key: String
        let relativePath: String
        let byteCount: Int64
        let lastAccessedAt: Date
    }

    private func managedRecord(for key: String) throws -> CachedResourceRecord? {
        let descriptor = FetchDescriptor<CachedResourceRecord>(
            predicate: #Predicate { $0.key == key }
        )
        return try modelContext.fetch(descriptor).first
    }

    func record(for key: String) throws -> Record? {
        guard let record = try managedRecord(for: key) else { return nil }
        return Record(
            key: record.key,
            relativePath: record.relativePath,
            byteCount: record.byteCount,
            lastAccessedAt: record.lastAccessedAt
        )
    }

    func upsert(key: String, relativePath: String, byteCount: Int64) throws {
        if let existing = try managedRecord(for: key) {
            existing.relativePath = relativePath
            existing.byteCount = byteCount
            existing.lastAccessedAt = .now
        } else {
            modelContext.insert(
                CachedResourceRecord(
                    key: key,
                    relativePath: relativePath,
                    byteCount: byteCount
                )
            )
        }
        try modelContext.save()
    }

    func touch(key: String) throws {
        guard let record = try managedRecord(for: key) else { return }
        record.lastAccessedAt = .now
        try modelContext.save()
    }

    func allByLeastRecentlyUsed() throws -> [Record] {
        let descriptor = FetchDescriptor<CachedResourceRecord>(
            sortBy: [SortDescriptor(\.lastAccessedAt)]
        )
        return try modelContext.fetch(descriptor).map {
            Record(
                key: $0.key,
                relativePath: $0.relativePath,
                byteCount: $0.byteCount,
                lastAccessedAt: $0.lastAccessedAt
            )
        }
    }

    func remove(key: String) throws {
        guard let record = try managedRecord(for: key) else { return }
        modelContext.delete(record)
        try modelContext.save()
    }

    func removeAll() throws {
        try modelContext.delete(model: CachedResourceRecord.self)
        try modelContext.save()
    }
}
