import Foundation
import OSLog

actor VideoCache {
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "VideoCache")
    private let cacheDirectory: URL
    private let maxCacheSize: Int64 = 1_073_741_824 // 1 GiB
    private var cacheIndex: [String: CacheEntry] = [:]
    private let fileManager = FileManager.default

    struct CacheEntry: Codable {
        let mediaID: String
        let fileURL: URL
        let fileSize: Int64
        let lastAccessDate: Date
    }

    init() {
        let caches = fileManager.urls(for: .cachesDirectory, in: .userDomainMask).first!
        self.cacheDirectory = caches.appendingPathComponent("com.comfygallery.video")
        try? fileManager.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
        Task { await loadIndex() }
    }

    func cachedURL(for mediaID: String) -> URL? {
        guard let entry = cacheIndex[mediaID],
              fileManager.fileExists(atPath: entry.fileURL.path) else {
            return nil
        }
        cacheIndex[mediaID] = CacheEntry(
            mediaID: entry.mediaID,
            fileURL: entry.fileURL,
            fileSize: entry.fileSize,
            lastAccessDate: Date()
        )
        return entry.fileURL
    }

    func store(mediaID: String, sourceURL: URL) throws -> URL {
        let destination = cacheDirectory.appendingPathComponent("\(mediaID).mp4")
        try? fileManager.removeItem(at: destination)
        try fileManager.moveItem(at: sourceURL, to: destination)
        let attributes = try fileManager.attributesOfItem(atPath: destination.path)
        let fileSize = (attributes[.size] as? Int64) ?? 0
        cacheIndex[mediaID] = CacheEntry(
            mediaID: mediaID,
            fileURL: destination,
            fileSize: fileSize,
            lastAccessDate: Date()
        )
        evictIfNeeded()
        saveIndex()
        return destination
    }

    func remove(mediaID: String) {
        if let entry = cacheIndex[mediaID] {
            try? fileManager.removeItem(at: entry.fileURL)
            cacheIndex[mediaID] = nil
            saveIndex()
        }
    }

    func clearAll() {
        try? fileManager.removeItem(at: cacheDirectory)
        try? fileManager.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
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
            try? fileManager.removeItem(at: entry.fileURL)
            cacheIndex[entry.mediaID] = nil
            size -= entry.fileSize
        }
    }

    private func loadIndex() {
        let indexURL = cacheDirectory.appendingPathComponent("index.json")
        guard let data = try? Data(contentsOf: indexURL),
              let entries = try? JSONDecoder().decode([CacheEntry].self, from: data) else {
            return
        }
        for entry in entries {
            cacheIndex[entry.mediaID] = entry
        }
    }

    private func saveIndex() {
        let indexURL = cacheDirectory.appendingPathComponent("index.json")
        let entries = Array(cacheIndex.values)
        if let data = try? JSONEncoder().encode(entries) {
            try? data.write(to: indexURL, options: .atomic)
        }
    }
}
