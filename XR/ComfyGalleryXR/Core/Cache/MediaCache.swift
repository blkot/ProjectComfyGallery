import Foundation
import SwiftData

enum CachedResourceKind: String, Codable, Sendable {
    case gridPreview = "grid-preview"
    case viewerPreview = "viewer-preview"
    case originalImage = "original-image"
    case spatialInput = "spatial-input"
    case videoPlayback = "video-playback"
    case spatialVideoPlayback = "spatial-video-playback"
}

struct MediaCacheKey: Hashable, Sendable {
    let profileID: UUID
    let mediaID: UUID
    let kind: CachedResourceKind
    let resourceID: UUID?

    init(
        profileID: UUID,
        mediaID: UUID,
        kind: CachedResourceKind,
        resourceID: UUID? = nil
    ) {
        self.profileID = profileID
        self.mediaID = mediaID
        self.kind = kind
        self.resourceID = resourceID
    }

    var identifier: String {
        let base =
            "\(profileID.uuidString.lowercased())/\(mediaID.uuidString.lowercased())/\(kind.rawValue)"
        guard let resourceID else { return base }
        return "\(base)/\(resourceID.uuidString.lowercased())"
    }
}

enum MediaCacheError: Error, Sendable {
    case missingBaseDirectory
    case invalidRecord
}

actor MediaCache {
    private let rootURL: URL
    private let byteBudget: Int64
    private let index: CacheIndexStore
    private let fileManager: FileManager

    init(
        modelContainer: ModelContainer,
        rootURL: URL? = nil,
        byteBudget: Int64 = 2 * 1_024 * 1_024 * 1_024,
        fileManager: FileManager = .default
    ) throws {
        self.fileManager = fileManager
        self.byteBudget = byteBudget
        index = CacheIndexStore(modelContainer: modelContainer)
        if let rootURL {
            self.rootURL = rootURL
        } else {
            guard let caches = fileManager.urls(for: .cachesDirectory, in: .userDomainMask).first else {
                throw MediaCacheError.missingBaseDirectory
            }
            self.rootURL = caches.appending(path: "ComfyGalleryXR/Media", directoryHint: .isDirectory)
        }
        try fileManager.createDirectory(
            at: self.rootURL,
            withIntermediateDirectories: true
        )
    }

    func file(for key: MediaCacheKey) async -> URL? {
        guard let record = try? await index.record(for: key.identifier) else {
            return nil
        }
        let url = rootURL.appending(path: record.relativePath)
        guard fileManager.fileExists(atPath: url.path) else {
            try? await index.remove(key: key.identifier)
            return nil
        }
        try? await index.touch(key: key.identifier)
        return url
    }

    func store(
        _ data: Data,
        for key: MediaCacheKey,
        mimeType: String?
    ) async throws -> URL {
        let relativePath = relativePath(for: key, mimeType: mimeType)
        let destination = rootURL.appending(path: relativePath)
        let directory = destination.deletingLastPathComponent()
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)

        let temporary = directory.appending(
            path: ".\(UUID().uuidString.lowercased()).partial"
        )
        do {
            try data.write(to: temporary, options: [.atomic])
            if fileManager.fileExists(atPath: destination.path) {
                _ = try fileManager.replaceItemAt(destination, withItemAt: temporary)
            } else {
                try fileManager.moveItem(at: temporary, to: destination)
            }
            try await index.upsert(
                key: key.identifier,
                relativePath: relativePath,
                byteCount: Int64(data.count)
            )
            try await evictIfNeeded(protecting: key.identifier)
            return destination
        } catch {
            try? fileManager.removeItem(at: temporary)
            throw error
        }
    }

    func clearAll() async throws {
        if fileManager.fileExists(atPath: rootURL.path) {
            try fileManager.removeItem(at: rootURL)
        }
        try fileManager.createDirectory(at: rootURL, withIntermediateDirectories: true)
        try await index.removeAll()
    }

    private func relativePath(for key: MediaCacheKey, mimeType: String?) -> String {
        let profile = key.profileID.uuidString.lowercased()
        let media = key.mediaID.uuidString.lowercased()
        let extensionName = Self.fileExtension(for: mimeType)
        let resourceSuffix = key.resourceID.map {
            "-\($0.uuidString.lowercased())"
        } ?? ""
        return "\(profile)/\(media)/\(key.kind.rawValue)\(resourceSuffix).\(extensionName)"
    }

    private func evictIfNeeded(protecting protectedKey: String) async throws {
        let records = try await index.allByLeastRecentlyUsed()
        var total = records.reduce(Int64.zero) { $0 + $1.byteCount }
        guard total > byteBudget else { return }

        for record in records where record.key != protectedKey {
            let url = rootURL.appending(path: record.relativePath)
            try? fileManager.removeItem(at: url)
            try await index.remove(key: record.key)
            total -= record.byteCount
            if total <= byteBudget { break }
        }
    }

    nonisolated static func fileExtension(for mimeType: String?) -> String {
        switch mimeType?.lowercased() {
        case "image/jpeg": "jpg"
        case "image/png": "png"
        case "image/webp": "webp"
        case "video/mp4": "mp4"
        case "video/quicktime": "mov"
        case "video/webm": "webm"
        default: "bin"
        }
    }
}
