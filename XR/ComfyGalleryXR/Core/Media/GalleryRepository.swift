import Foundation

actor GalleryRepository {
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

    func detail(id: UUID) async throws -> XRMediaDetail {
        try await api.get(
            XRMediaDetail.self,
            path: "/api/v1/media/\(id.uuidString.lowercased())"
        )
    }

    func navigation(id: UUID, scope: GalleryScope) async throws -> MediaNavigation {
        try await api.get(
            MediaNavigation.self,
            path: "/api/v1/media/\(id.uuidString.lowercased())/navigation",
            queryItems: queryItems(for: scope)
        )
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
        var items = [
            URLQueryItem(name: "status", value: "ready"),
            URLQueryItem(name: "sort", value: scope.sort.rawValue)
        ]
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
