import Foundation
import UIKit
import OSLog
import UniformTypeIdentifiers

actor MediaRepository {
    private let apiClient: APIClient
    private let videoCache: VideoCache
    private let imageCache = NSCache<NSString, UIImage>()
    private var activeTasks: [String: Task<Data, Error>] = [:]
    private var activeVideoTasks: [String: Task<URL, Error>] = [:]
    private var originalTasks: [String: Task<UIImage, Error>] = [:]
    private var originalRequestIDs: [String: UUID] = [:]
    private var videoRequestIDs: [String: UUID] = [:]
    private var cacheGeneration = 0
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "MediaRepository")

    init(apiClient: APIClient, videoCache: VideoCache = VideoCache()) {
        self.apiClient = apiClient
        self.videoCache = videoCache
        imageCache.countLimit = 200
        imageCache.totalCostLimit = 96 * 1024 * 1024 // Current page plus two display-sized neighbors.
        NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { await self?.handleMemoryWarning() }
        }
    }

    func fetchPreviewImage(mediaID: String, targetSize: CGSize, scale: CGFloat = 3) async throws -> UIImage? {
        let generation = cacheGeneration
        let cacheKey = "preview_\(mediaID)_\(Int(targetSize.width * scale))x\(Int(targetSize.height * scale))" as NSString
        if let cached = imageCache.object(forKey: cacheKey) {
            return cached
        }
        if let existing = activeTasks[mediaID] {
            let data = try await existing.value
            try Task.checkCancellation()
            guard generation == cacheGeneration else { throw CancellationError() }
            return ImageDecoder.downsample(data: data, to: targetSize, scale: scale)
        }
        let task = Task<Data, Error> {
            return try await apiClient.requestData(.mediaPreview(id: mediaID))
        }
        activeTasks[mediaID] = task
        defer { if generation == cacheGeneration { activeTasks[mediaID] = nil } }

        let data = try await task.value
        try Task.checkCancellation()
        guard generation == cacheGeneration else { throw CancellationError() }
        guard let image = ImageDecoder.downsample(data: data, to: targetSize, scale: scale) else {
            throw APIError.invalidResponse
        }
        imageCache.setObject(image, forKey: cacheKey, cost: imageCost(image))
        return image
    }

    func fetchOriginalImage(mediaID: String, targetSize: CGSize, scale: CGFloat) async throws -> UIImage {
        let generation = cacheGeneration
        let pixelSize = min(ViewerPreloadPolicy.maximumImagePixels, max(targetSize.width, targetSize.height) * scale)
        let cacheKey = "original_\(mediaID)_\(Int(pixelSize))" as NSString
        if let cached = imageCache.object(forKey: cacheKey) { return cached }
        if let existing = originalTasks[mediaID], !existing.isCancelled {
            let image = try await existing.value
            try Task.checkCancellation()
            guard generation == cacheGeneration else { throw CancellationError() }
            imageCache.setObject(image, forKey: cacheKey, cost: imageCost(image))
            return image
        }
        let requestID = UUID()
        let task = Task<UIImage, Error> {
            let temporaryURL = FileManager.default.temporaryDirectory.appendingPathComponent("gallery_image_\(UUID().uuidString)")
            defer { try? FileManager.default.removeItem(at: temporaryURL) }
            _ = try await apiClient.download(.mediaOriginal(id: mediaID), to: temporaryURL)
            try Task.checkCancellation()
            guard let image = ImageDecoder.downsample(fileURL: temporaryURL, maxPixelSize: pixelSize) else { throw APIError.invalidResponse }
            return image
        }
        originalTasks[mediaID] = task
        originalRequestIDs[mediaID] = requestID
        defer {
            if originalRequestIDs[mediaID] == requestID { originalTasks[mediaID] = nil; originalRequestIDs[mediaID] = nil }
        }
        let image = try await task.value
        try Task.checkCancellation()
        guard generation == cacheGeneration else { throw CancellationError() }
        imageCache.setObject(image, forKey: cacheKey, cost: imageCost(image))
        return image
    }

    func prepareViewerWindow(currentID: String, neighbors: [MobileMediaSummary], targetSize: CGSize, scale: CGFloat) async {
        let neighbors = ViewerPreloadPolicy.neighbors(currentID: currentID, candidates: neighbors)
        let allowed = Set(neighbors.map(\.id) + [currentID])
        for (id, task) in originalTasks where !allowed.contains(id) { task.cancel() }
        for (id, task) in activeVideoTasks where !allowed.contains(id) { task.cancel() }
        await withTaskGroup(of: Void.self) { group in
            for item in neighbors.prefix(2) {
                group.addTask {
                    _ = try? await self.fetchPreviewImage(mediaID: item.id, targetSize: targetSize, scale: scale)
                    guard !Task.isCancelled else { return }
                    if item.kind == .image {
                        _ = try? await self.fetchOriginalImage(mediaID: item.id, targetSize: targetSize, scale: scale)
                    } else if ViewerPreloadPolicy.preloadVideo(item) {
                        // Avoid silently downloading large neighboring videos over a mobile connection.
                        _ = try? await self.fetchPlaybackVideo(mediaID: item.id)
                    }
                }
            }
        }
    }

    func endViewerPrefetch() {
        for task in originalTasks.values { task.cancel() }
        for task in activeVideoTasks.values { task.cancel() }
    }

    func fetchPlaybackVideo(mediaID: String) async throws -> URL {
        if let cached = await videoCache.cachedURL(for: mediaID) {
            return cached
        }
        if let existing = activeVideoTasks[mediaID], !existing.isCancelled {
            return try await existing.value
        }
        let requestID = UUID()
        let task = Task<URL, Error> {
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent("video_download_\(UUID().uuidString)")
            defer { try? FileManager.default.removeItem(at: tempURL) }
            let response = try await apiClient.download(.mediaPlayback(id: mediaID), to: tempURL)
            try Task.checkCancellation()
            let suggested = suggestedExtension(from: response) ?? "mp4"
            let cachedURL = try await videoCache.store(
                mediaID: mediaID,
                sourceURL: tempURL,
                suggestedExtension: suggested
            )
            return cachedURL
        }
        activeVideoTasks[mediaID] = task
        videoRequestIDs[mediaID] = requestID
        defer {
            if videoRequestIDs[mediaID] == requestID {
                activeVideoTasks[mediaID] = nil
                videoRequestIDs[mediaID] = nil
            }
        }

        return try await task.value
    }

    func cancelFetch(for mediaID: String) {
        activeTasks[mediaID]?.cancel()
        activeTasks[mediaID] = nil
        cancelVideoFetch(for: mediaID)
    }

    func cancelVideoFetch(for mediaID: String) {
        activeVideoTasks[mediaID]?.cancel()
        activeVideoTasks[mediaID] = nil
        videoRequestIDs[mediaID] = nil
    }

    func clearImageCache() {
        imageCache.removeAllObjects()
    }

    func clearVideoCache() async {
        await videoCache.clearAll()
    }

    func clearAllCaches() async {
        cacheGeneration += 1
        let videoTasks = Array(activeVideoTasks.values)
        for task in activeTasks.values { task.cancel() }
        for task in originalTasks.values { task.cancel() }
        originalTasks.removeAll()
        originalRequestIDs.removeAll()
        for task in activeVideoTasks.values { task.cancel() }
        activeTasks.removeAll()
        activeVideoTasks.removeAll()
        videoRequestIDs.removeAll()
        clearImageCache()
        // Drain in-flight cache writes before deleting their files.
        for task in videoTasks { _ = try? await task.value }
        await videoCache.clearAll()
    }

    private func imageCost(_ image: UIImage) -> Int {
        guard let cgImage = image.cgImage else { return 0 }
        return cgImage.bytesPerRow * cgImage.height
    }

    func currentCacheBytes() async -> Int64 {
        return await videoCache.currentSize
    }

    private func handleMemoryWarning() {
        imageCache.removeAllObjects()
    }

    private func suggestedExtension(from response: HTTPURLResponse) -> String? {
        guard let contentType = response.value(forHTTPHeaderField: "Content-Type"),
              let utType = UTType(mimeType: contentType) else {
            return nil
        }
        return utType.preferredFilenameExtension
    }
}
