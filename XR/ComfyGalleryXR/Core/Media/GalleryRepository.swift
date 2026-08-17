import Foundation

actor GalleryRepository {
    private enum NeighborDirection {
        case previous
        case next
    }

    private struct PlaybackPreferenceBody: Encodable, Sendable {
        let prefersSpatialPlayback: Bool

        enum CodingKeys: String, CodingKey {
            case prefersSpatialPlayback = "prefer_spatial_playback"
        }
    }

    private struct FavoriteBody: Encodable, Sendable {
        let favorite: Bool
    }

    private let api: APIClient

    init(api: APIClient) {
        self.api = api
    }

    func page(scope: GalleryScope, limit: Int = 48, offset: Int) async throws -> MediaPage {
        try await api.get(
            MediaPage.self,
            path: "/api/v1/media",
            queryItems: queryItems(for: scope) + [
                URLQueryItem(name: "limit", value: String(limit)),
                URLQueryItem(name: "offset", value: String(offset))
            ]
        )
    }

    /// Fetches enough raw server pages to produce one useful visible batch after
    /// XR filters out transient and failed media statuses. Raw page boundaries
    /// remain intact so subsequent offsets continue to match the backend stream.
    func playablePages(
        scope: GalleryScope,
        visibleLimit: Int = 48,
        offset: Int
    ) async throws -> [MediaPage] {
        var pages: [MediaPage] = []
        var rawOffset = offset
        var visibleCount = 0

        repeat {
            try Task.checkCancellation()
            let remainingVisibleCount = max(1, visibleLimit - visibleCount)
            let page = try await page(
                scope: scope,
                limit: remainingVisibleCount,
                offset: rawOffset
            )
            pages.append(page)
            visibleCount += page.items.count(where: GalleryMediaVisibility.includes)

            let nextRawOffset = page.offset + page.items.count
            let isExhausted = page.items.count < page.limit || nextRawOffset >= page.total
            guard !isExhausted, nextRawOffset > rawOffset else { break }
            rawOffset = nextRawOffset
        } while visibleCount < visibleLimit

        return pages
    }

    func detail(id: UUID) async throws -> XRMediaDetail {
        try await api.get(
            XRMediaDetail.self,
            path: "/api/v1/media/\(id.uuidString.lowercased())"
        )
    }

    func navigation(id: UUID, scope: GalleryScope) async throws -> MediaNavigation {
        let raw = try await rawNavigation(id: id, scope: scope)
        async let previous = playableNeighbor(
            startingAt: raw.previousID,
            position: raw.previousPosition,
            direction: .previous,
            scope: scope
        )
        async let next = playableNeighbor(
            startingAt: raw.nextID,
            position: raw.nextPosition,
            direction: .next,
            scope: scope
        )
        let (resolvedPrevious, resolvedNext) = try await (previous, next)
        return MediaNavigation(
            mediaID: raw.mediaID,
            position: raw.position,
            total: raw.total,
            previousID: resolvedPrevious?.id,
            previousPosition: resolvedPrevious?.position,
            nextID: resolvedNext?.id,
            nextPosition: resolvedNext?.position
        )
    }

    private func rawNavigation(id: UUID, scope: GalleryScope) async throws -> MediaNavigation {
        try await api.get(
            MediaNavigation.self,
            path: "/api/v1/media/\(id.uuidString.lowercased())/navigation",
            queryItems: queryItems(for: scope)
        )
    }

    private func playableNeighbor(
        startingAt initialID: UUID?,
        position initialPosition: Int?,
        direction: NeighborDirection,
        scope: GalleryScope
    ) async throws -> (id: UUID, position: Int)? {
        var candidateID = initialID
        var candidatePosition = initialPosition
        var visited: Set<UUID> = []

        while let mediaID = candidateID, let position = candidatePosition {
            try Task.checkCancellation()
            guard visited.insert(mediaID).inserted else { return nil }
            let candidate = try await detail(id: mediaID)
            if GalleryMediaVisibility.includes(candidate) {
                return (mediaID, position)
            }

            let navigation = try await rawNavigation(id: mediaID, scope: scope)
            switch direction {
            case .previous:
                candidateID = navigation.previousID
                candidatePosition = navigation.previousPosition
            case .next:
                candidateID = navigation.nextID
                candidatePosition = navigation.nextPosition
            }
        }

        return nil
    }

    func updatePlaybackPreference(
        id: UUID,
        isPreferred: Bool
    ) async throws -> MediaPlaybackPreferenceResponse {
        try await api.put(
            MediaPlaybackPreferenceResponse.self,
            path: "/api/v1/media/\(id.uuidString.lowercased())/playback-preference",
            body: PlaybackPreferenceBody(prefersSpatialPlayback: isPreferred)
        )
    }

    func updateFavorite(id: UUID, isFavorite: Bool) async throws -> MediaFavoriteResponse {
        try await api.put(
            MediaFavoriteResponse.self,
            path: "/api/v1/media/\(id.uuidString.lowercased())/favorite",
            body: FavoriteBody(favorite: isFavorite)
        )
    }

    private func queryItems(for scope: GalleryScope) -> [URLQueryItem] {
        var items = [URLQueryItem(name: "sort", value: scope.sort.rawValue)]
        if let kind = scope.kind.queryValue {
            items.append(URLQueryItem(name: "kind", value: kind))
        }
        if !scope.includesTrash {
            items.append(URLQueryItem(name: "trash", value: "false"))
        }
        switch scope.preference {
        case .all:
            break
        case .favorites:
            items.append(URLQueryItem(name: "favorite", value: "true"))
        case .spatial:
            items.append(URLQueryItem(name: "prefer_spatial_playback", value: "true"))
        }
        return items
    }
}
