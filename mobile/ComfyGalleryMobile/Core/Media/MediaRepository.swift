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
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "MediaRepository")

    init(apiClient: APIClient, videoCache: VideoCache = VideoCache()) {
        self.apiClient = apiClient
        self.videoCache = videoCache
        imageCache.countLimit = 200
        imageCache.totalCostLimit = 50 * 1024 * 1024 // 50 MB
        NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { await self?.handleMemoryWarning() }
        }
    }

    func fetchPreviewImage(mediaID: String, targetSize: CGSize) async throws -> UIImage? {
        let cacheKey = "\(mediaID)_\(Int(targetSize.width))x\(Int(targetSize.height))" as NSString
        if let cached = imageCache.object(forKey: cacheKey) {
            return cached
        }
        if let existing = activeTasks[mediaID] {
            let data = try await existing.value
            return ImageDecoder.downsample(data: data, to: targetSize, scale: 3.0)
        }
        let task = Task<Data, Error> {
            return try await apiClient.requestData(.mediaPreview(id: mediaID))
        }
        activeTasks[mediaID] = task
        defer { activeTasks[mediaID] = nil }

        let data = try await task.value
        guard let image = ImageDecoder.downsample(data: data, to: targetSize, scale: 3.0) else {
            throw APIError.invalidResponse
        }
        imageCache.setObject(image, forKey: cacheKey)
        return image
    }

    func fetchPlaybackVideo(mediaID: String) async throws -> URL {
        if let cached = await videoCache.cachedURL(for: mediaID) {
            return cached
        }
        if let existing = activeVideoTasks[mediaID] {
            return try await existing.value
        }
        let task = Task<URL, Error> {
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent("video_download_\(UUID().uuidString)")
            let response = try await apiClient.download(.mediaPlayback(id: mediaID), to: tempURL)
            let suggested = suggestedExtension(from: response) ?? "mp4"
            let cachedURL = try await videoCache.store(
                mediaID: mediaID,
                sourceURL: tempURL,
                suggestedExtension: suggested
            )
            return cachedURL
        }
        activeVideoTasks[mediaID] = task
        defer { activeVideoTasks[mediaID] = nil }

        return try await task.value
    }

    func cancelFetch(for mediaID: String) {
        activeTasks[mediaID]?.cancel()
        activeTasks[mediaID] = nil
        activeVideoTasks[mediaID]?.cancel()
        activeVideoTasks[mediaID] = nil
    }

    func clearImageCache() {
        imageCache.removeAllObjects()
    }

    func clearVideoCache() async {
        await videoCache.clearAll()
    }

    func clearAllCaches() async {
        clearImageCache()
        await videoCache.clearAll()
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
