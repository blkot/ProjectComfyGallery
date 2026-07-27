import Foundation
import ImageIO
import UIKit

final class DecodedImage: @unchecked Sendable {
    let image: UIImage

    init(image: UIImage) {
        self.image = image
    }
}
actor AsyncGate {
    private let limit: Int
    private var active = 0
    private var waiters: [CheckedContinuation<Void, Never>] = []

    init(limit: Int) {
        self.limit = max(1, limit)
    }

    func acquire() async {
        if active < limit {
            active += 1
            return
        }
        await withCheckedContinuation { continuation in
            waiters.append(continuation)
        }
    }

    func release() {
        if waiters.isEmpty {
            active = max(0, active - 1)
        } else {
            waiters.removeFirst().resume()
        }
    }
}

enum ImagePipelineError: LocalizedError, Sendable {
    case unsupportedContent
    case decodeFailed

    var errorDescription: String? {
        switch self {
        case .unsupportedContent: "The server returned an unsupported image."
        case .decodeFailed: "The image could not be decoded."
        }
    }
}

actor ImagePipeline {
    private let api: APIClient
    private let cache: MediaCache
    private let gate = AsyncGate(limit: 4)
    private let memory = NSCache<NSString, DecodedImage>()

    init(api: APIClient, cache: MediaCache) {
        self.api = api
        self.cache = cache
        memory.totalCostLimit = 256 * 1_024 * 1_024
        memory.countLimit = 120
    }

    func image(
        profileID: UUID,
        mediaID: UUID,
        path: String,
        resourceKind: CachedResourceKind,
        targetPixelSize: CGSize
    ) async throws -> DecodedImage {
        let targetMaximum = max(targetPixelSize.width, targetPixelSize.height)
        let memoryKey = "\(profileID.uuidString):\(mediaID.uuidString):\(resourceKind.rawValue):\(Int(targetMaximum))"
        if let cached = memory.object(forKey: memoryKey as NSString) {
            return cached
        }

        let key = MediaCacheKey(profileID: profileID, mediaID: mediaID, kind: resourceKind)
        let data: Data
        if let file = await cache.file(for: key) {
            data = try Data(contentsOf: file, options: [.mappedIfSafe])
        } else {
            await gate.acquire()
            do {
                let payload = try await api.download(path: path)
                guard payload.mimeType?.hasPrefix("image/") == true else {
                    throw ImagePipelineError.unsupportedContent
                }
                _ = try await cache.store(payload.data, for: key, mimeType: payload.mimeType)
                data = payload.data
                await gate.release()
            } catch {
                await gate.release()
                throw error
            }
        }

        try Task.checkCancellation()
        let decoded = try await Self.downsample(data: data, maximumPixelDimension: targetMaximum)
        memory.setObject(
            decoded,
            forKey: memoryKey as NSString,
            cost: decoded.image.cgImage.map { $0.bytesPerRow * $0.height } ?? data.count
        )
        return decoded
    }

    func clearMemory() {
        memory.removeAllObjects()
    }

    nonisolated private static func downsample(
        data: Data,
        maximumPixelDimension: CGFloat
    ) async throws -> DecodedImage {
        try await Task.detached(priority: .utility) {
            guard let source = CGImageSourceCreateWithData(data as CFData, nil) else {
                throw ImagePipelineError.decodeFailed
            }
            let options: [CFString: Any] = [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceShouldCacheImmediately: true,
                kCGImageSourceThumbnailMaxPixelSize: max(1, Int(maximumPixelDimension))
            ]
            guard let cgImage = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
                throw ImagePipelineError.decodeFailed
            }
            return DecodedImage(image: UIImage(cgImage: cgImage))
        }.value
    }
}
