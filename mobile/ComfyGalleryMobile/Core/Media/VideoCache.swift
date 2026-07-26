import Foundation
import OSLog
import UniformTypeIdentifiers

actor VideoCache {
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "VideoCache")
    private let cacheDirectory: URL
    private let maxCacheSize: Int64 = 1_073_741_824 // 1 GiB
    private var cacheIndex: [String: CacheEntry] = [:]
    private let indexURL: URL

    struct CacheEntry: Codable {
        let mediaID: String
        let fileURL: URL
        let fileSize: Int64
        let lastAccessDate: Date
        let fileExtension: String
    }

    init() {
        let fm = FileManager.default
        let caches = fm.urls(for: .cachesDirectory, in: .userDomainMask).first
            ?? fm.temporaryDirectory
        self.cacheDirectory = caches.appendingPathComponent("com.comfygallery.video")
        self.indexURL = cacheDirectory.appendingPathComponent("index.json")
        try? fm.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
        self.cacheIndex = Self.loadIndex(from: indexURL, fileManager: fm)
    }

    func cachedURL(for mediaID: String) -> URL? {
        guard let entry = cacheIndex[mediaID],
              FileManager.default.fileExists(atPath: entry.fileURL.path) else {
            return nil
        }
        cacheIndex[mediaID] = CacheEntry(
            mediaID: entry.mediaID,
            fileURL: entry.fileURL,
            fileSize: entry.fileSize,
            lastAccessDate: Date(),
            fileExtension: entry.fileExtension
        )
        return entry.fileURL
    }

    func store(mediaID: String, sourceURL: URL, suggestedExtension: String = "mp4") throws -> URL {
        let ext = Self.extensionFor(sourceURL: sourceURL, fallback: suggestedExtension)
        let destination = cacheDirectory.appendingPathComponent("\(mediaID).\(ext)")
        let fm = FileManager.default
        try? fm.removeItem(at: destination)
        try fm.moveItem(at: sourceURL, to: destination)
        let attributes = try fm.attributesOfItem(atPath: destination.path)
        let fileSize = (attributes[.size] as? Int64) ?? 0
        cacheIndex[mediaID] = CacheEntry(
            mediaID: mediaID,
            fileURL: destination,
            fileSize: fileSize,
            lastAccessDate: Date(),
            fileExtension: ext
        )
        evictIfNeeded()
        saveIndex()
        return destination
    }

    func remove(mediaID: String) {
        if let entry = cacheIndex[mediaID] {
            try? FileManager.default.removeItem(at: entry.fileURL)
            cacheIndex[mediaID] = nil
            saveIndex()
        }
    }

    func clearAll() {
        let fm = FileManager.default
        try? fm.removeItem(at: cacheDirectory)
        try? fm.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
        cacheIndex.removeAll()
        saveIndex()
    }

    var currentSize: Int64 {
        cacheIndex.values.reduce(0) { $0 + $1.fileSize }
    }

    private func evictIfNeeded() {
        let sorted = cacheIndex.values.sorted { $0.lastAccessDate < $1.lastAccessDate }
        var size = currentSize
        for entry in sorted {
            guard size > maxCacheSize else { break }
            try? FileManager.default.removeItem(at: entry.fileURL)
            cacheIndex[entry.mediaID] = nil
            size -= entry.fileSize
        }
    }

    private func saveIndex() {
        let entries = Array(cacheIndex.values)
        if let data = try? JSONEncoder().encode(entries) {
            try? data.write(to: indexURL, options: .atomic)
        }
    }

    private static func loadIndex(from indexURL: URL, fileManager: FileManager) -> [String: CacheEntry] {
        guard let data = try? Data(contentsOf: indexURL),
              let entries = try? JSONDecoder().decode([CacheEntry].self, from: data) else {
            return [:]
        }
        var validEntries: [String: CacheEntry] = [:]
        for entry in entries {
            guard fileManager.fileExists(atPath: entry.fileURL.path) else { continue }
            validEntries[entry.mediaID] = entry
        }
        return validEntries
    }

    private static func extensionFor(sourceURL: URL, fallback: String) -> String {
        if let utType = UTType(filenameExtension: sourceURL.pathExtension),
           utType.conforms(to: .audiovisualContent) {
            let ext = utType.preferredFilenameExtension ?? sourceURL.pathExtension
            return ext.isEmpty ? fallback : ext
        }
        let pathExt = sourceURL.pathExtension
        return pathExt.isEmpty ? fallback : pathExt
    }
}
