import Foundation

actor MediaRepository {
    private let api: APIClient
    private let cache: MediaCache
    private let imagePipeline: ImagePipeline

    init(api: APIClient, cache: MediaCache, imagePipeline: ImagePipeline) {
        self.api = api
        self.cache = cache
        self.imagePipeline = imagePipeline
    }

    func preview(
        profileID: UUID,
        media: XRMediaSummary,
        targetPixelSize: CGSize
    ) async throws -> DecodedImage {
        try await imagePipeline.image(
            profileID: profileID,
            mediaID: media.id,
            path: media.previewPath,
            resourceKind: .gridPreview,
            targetPixelSize: targetPixelSize
        )
    }

    func viewerImage(
        profileID: UUID,
        media: XRMediaDetail,
        targetPixelSize: CGSize
    ) async throws -> DecodedImage {
        try await imagePipeline.image(
            profileID: profileID,
            mediaID: media.id,
            path: media.previewPath,
            resourceKind: .viewerPreview,
            targetPixelSize: targetPixelSize
        )
    }

    func originalImageFile(profileID: UUID, media: XRMediaDetail) async throws -> URL {
        let key = MediaCacheKey(
            profileID: profileID,
            mediaID: media.id,
            kind: .originalImage
        )
        if let cached = await cache.file(for: key) {
            return cached
        }
        let payload = try await api.download(path: media.originalPath)
        guard payload.mimeType?.hasPrefix("image/") == true else {
            throw ImagePipelineError.unsupportedContent
        }
        return try await cache.store(payload.data, for: key, mimeType: payload.mimeType)
    }

    func spatialImageFile(profileID: UUID, media: XRMediaDetail) async throws -> URL {
        let key = MediaCacheKey(
            profileID: profileID,
            mediaID: media.id,
            kind: .spatialInput
        )
        if let cached = await cache.file(for: key) {
            return cached
        }

        let originalURL = try await originalImageFile(profileID: profileID, media: media)
        let normalizedData = try await SpatialInputNormalizer.normalizedJPEGData(
            contentsOf: originalURL
        )
        return try await cache.store(normalizedData, for: key, mimeType: "image/jpeg")
    }

    func videoFile(profileID: UUID, media: XRMediaDetail) async throws -> URL {
        guard let source = media.selectedVideoPlaybackSource else {
            throw APIClientError.invalidResponse
        }
        let key: MediaCacheKey
        switch source.representation {
        case .ordinary:
            key = MediaCacheKey(
                profileID: profileID,
                mediaID: media.id,
                kind: .videoPlayback
            )
        case .spatial(let variantID):
            key = MediaCacheKey(
                profileID: profileID,
                mediaID: media.id,
                kind: .spatialVideoPlayback,
                resourceID: variantID
            )
        }
        if let cached = await cache.file(for: key) {
            return cached
        }
        let payload = try await api.download(path: source.path)
        let mimeType = payload.mimeType ?? source.mimeType
        guard mimeType?.hasPrefix("video/") == true else {
            throw APIClientError.invalidContentType
        }
        return try await cache.store(payload.data, for: key, mimeType: mimeType)
    }

    func clearMemory() async {
        await imagePipeline.clearMemory()
    }
}
