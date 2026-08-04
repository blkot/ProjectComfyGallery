import Foundation

struct ServerProfile: Codable, Hashable, Identifiable, Sendable {
    let id: UUID
    let baseURL: URL
    let createdAt: Date

    init(id: UUID = UUID(), baseURL: URL, createdAt: Date = .now) {
        self.id = id
        self.baseURL = baseURL
        self.createdAt = createdAt
    }
}

struct Health: Decodable, Sendable {
    let status: String
    let service: String
    let version: String
}

struct AuthenticatedUser: Decodable, Hashable, Identifiable, Sendable {
    let id: UUID
    let username: String
}

struct AuthenticatedSession: Decodable, Sendable {
    let user: AuthenticatedUser
}

enum MediaKind: Hashable, Sendable {
    case image
    case video
    case unsupported(String)

    var queryValue: String? {
        switch self {
        case .image: "image"
        case .video: "video"
        case .unsupported: nil
        }
    }

    var isImage: Bool { self == .image }
    var isVideo: Bool { self == .video }
}

extension MediaKind: Codable {
    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer().decode(String.self)
        switch value {
        case "image": self = .image
        case "video": self = .video
        default: self = .unsupported(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .image: try container.encode("image")
        case .video: try container.encode("video")
        case .unsupported(let value): try container.encode(value)
        }
    }
}

enum GalleryKindFilter: String, Codable, CaseIterable, Identifiable, Sendable {
    case all
    case images
    case videos

    var id: Self { self }

    var queryValue: String? {
        switch self {
        case .all: nil
        case .images: "image"
        case .videos: "video"
        }
    }

    var title: String {
        switch self {
        case .all: "All"
        case .images: "Images"
        case .videos: "Videos"
        }
    }
}

enum GalleryPreferenceFilter: String, Codable, CaseIterable, Identifiable, Sendable {
    case all
    case favorites
    case spatial

    var id: Self { self }

    var title: String {
        switch self {
        case .all: "All Media"
        case .favorites: "Favorites"
        case .spatial: "Spatial"
        }
    }

    var systemImage: String {
        switch self {
        case .all: "rectangle.grid.2x2"
        case .favorites: "heart.fill"
        case .spatial: "cube.transparent"
        }
    }
}

enum MediaSort: String, Codable, CaseIterable, Identifiable, Sendable {
    case newest = "file_created_desc"
    case oldest = "file_created_asc"
    case importedNewest = "imported_desc"
    case importedOldest = "imported_asc"

    var id: Self { self }

    var title: String {
        switch self {
        case .newest: "Newest"
        case .oldest: "Oldest"
        case .importedNewest: "Recently Added"
        case .importedOldest: "First Added"
        }
    }
}

struct GalleryScope: Codable, Hashable, Sendable {
    var kind: GalleryKindFilter
    var preference: GalleryPreferenceFilter
    var includesTrash: Bool
    var sort: MediaSort

    init(
        kind: GalleryKindFilter = .all,
        preference: GalleryPreferenceFilter = .all,
        includesTrash: Bool = false,
        sort: MediaSort = .newest
    ) {
        self.kind = kind
        self.preference = preference
        self.includesTrash = includesTrash
        self.sort = sort
    }

    var id: String {
        "\(kind.rawValue):\(preference.rawValue):\(includesTrash):\(sort.rawValue)"
    }

    private enum CodingKeys: String, CodingKey {
        case kind, preference, includesTrash, sort
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        kind = try container.decodeIfPresent(GalleryKindFilter.self, forKey: .kind) ?? .all
        preference = try container.decodeIfPresent(
            GalleryPreferenceFilter.self,
            forKey: .preference
        ) ?? .all
        includesTrash = try container.decodeIfPresent(Bool.self, forKey: .includesTrash) ?? false
        sort = try container.decodeIfPresent(MediaSort.self, forKey: .sort) ?? .newest
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(kind, forKey: .kind)
        try container.encode(preference, forKey: .preference)
        try container.encode(includesTrash, forKey: .includesTrash)
        try container.encode(sort, forKey: .sort)
    }
}

struct MediaPreferences: Equatable, Sendable {
    var favorite: Bool
    var prefersSpatialPlayback: Bool
}

enum MediaPreferenceWrite: Equatable, Sendable {
    case favorite(Bool)
    case playbackPreference(Bool)
}

enum MediaPreferenceField: Hashable, Sendable {
    case favorite
    case playbackPreference
}

struct MediaPreferenceMutation: Equatable, Sendable {
    let preferences: MediaPreferences
    let fields: Set<MediaPreferenceField>
}

enum MediaPreferenceMutationPlan {
    static func runtimeSpatialImage(isEnabled: Bool) -> MediaPreferenceMutation {
        MediaPreferenceMutation(
            preferences: MediaPreferences(
                favorite: isEnabled,
                prefersSpatialPlayback: isEnabled
            ),
            fields: [.favorite, .playbackPreference]
        )
    }

    static func playbackPreference(
        isPreferred: Bool,
        preserving current: MediaPreferences
    ) -> MediaPreferenceMutation {
        MediaPreferenceMutation(
            preferences: MediaPreferences(
                favorite: current.favorite,
                prefersSpatialPlayback: isPreferred
            ),
            fields: [.playbackPreference]
        )
    }

    static func favorite(
        isFavorite: Bool,
        preserving current: MediaPreferences
    ) -> MediaPreferenceMutation {
        MediaPreferenceMutation(
            preferences: MediaPreferences(
                favorite: isFavorite,
                prefersSpatialPlayback: current.prefersSpatialPlayback
            ),
            fields: [.favorite]
        )
    }

    static func writes(
        fields: Set<MediaPreferenceField>,
        desired: MediaPreferences
    ) -> [MediaPreferenceWrite] {
        var writes: [MediaPreferenceWrite] = []
        if fields.contains(.favorite) {
            writes.append(.favorite(desired.favorite))
        }
        if fields.contains(.playbackPreference) {
            writes.append(.playbackPreference(desired.prefersSpatialPlayback))
        }
        return writes
    }
}

struct MediaPage: Decodable, Sendable {
    let items: [XRMediaSummary]
    let total: Int
    let limit: Int
    let offset: Int
}

struct XRMediaSummary: Decodable, Hashable, Identifiable, Sendable {
    let id: UUID
    let kind: MediaKind
    let status: String
    let mimeType: String?
    let width: Int?
    let height: Int?
    let durationSeconds: Double?
    let byteSize: Int64
    let isTrash: Bool
    let previewPath: String
    let spatialAvailable: Bool
    var prefersSpatialPlayback: Bool
    var favorite: Bool

    enum CodingKeys: String, CodingKey {
        case id, kind, status, width, height
        case mimeType = "mime_type"
        case durationSeconds = "duration_seconds"
        case byteSize = "byte_size"
        case isTrash = "is_trash"
        case previewPath = "preview_url"
        case spatialAvailable = "spatial_available"
        case prefersSpatialPlayback = "prefer_spatial_playback"
        case legacySpatialViewPreferred = "spatial_view_preferred"
        case favorite
    }

    init(
        id: UUID,
        kind: MediaKind,
        status: String,
        mimeType: String?,
        width: Int?,
        height: Int?,
        durationSeconds: Double?,
        byteSize: Int64,
        isTrash: Bool,
        previewPath: String,
        spatialAvailable: Bool = false,
        prefersSpatialPlayback: Bool = false,
        favorite: Bool = false
    ) {
        self.id = id
        self.kind = kind
        self.status = status
        self.mimeType = mimeType
        self.width = width
        self.height = height
        self.durationSeconds = durationSeconds
        self.byteSize = byteSize
        self.isTrash = isTrash
        self.previewPath = previewPath
        self.spatialAvailable = spatialAvailable
        self.prefersSpatialPlayback = prefersSpatialPlayback
        self.favorite = favorite
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        kind = try container.decode(MediaKind.self, forKey: .kind)
        status = try container.decode(String.self, forKey: .status)
        mimeType = try container.decodeIfPresent(String.self, forKey: .mimeType)
        width = try container.decodeIfPresent(Int.self, forKey: .width)
        height = try container.decodeIfPresent(Int.self, forKey: .height)
        durationSeconds = try container.decodeIfPresent(Double.self, forKey: .durationSeconds)
        byteSize = try container.decode(Int64.self, forKey: .byteSize)
        isTrash = try container.decode(Bool.self, forKey: .isTrash)
        previewPath = try container.decode(String.self, forKey: .previewPath)
        spatialAvailable = try container.decodeIfPresent(Bool.self, forKey: .spatialAvailable) ?? false
        prefersSpatialPlayback =
            try container.decodeIfPresent(Bool.self, forKey: .prefersSpatialPlayback)
            ?? container.decodeIfPresent(Bool.self, forKey: .legacySpatialViewPreferred)
            ?? false
        favorite = try container.decodeIfPresent(Bool.self, forKey: .favorite) ?? false
    }

    var preferences: MediaPreferences {
        get {
            MediaPreferences(
                favorite: favorite,
                prefersSpatialPlayback: prefersSpatialPlayback
            )
        }
        set {
            favorite = newValue.favorite
            prefersSpatialPlayback = newValue.prefersSpatialPlayback
        }
    }
}

enum MediaVariantRole: Hashable, Sendable {
    case spatialVideo
    case unsupported(String)
}

extension MediaVariantRole: Codable {
    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer().decode(String.self)
        switch value {
        case "spatial_video": self = .spatialVideo
        default: self = .unsupported(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .spatialVideo: try container.encode("spatial_video")
        case .unsupported(let value): try container.encode(value)
        }
    }
}

struct XRMediaVariant: Decodable, Hashable, Identifiable, Sendable {
    let id: UUID
    let role: MediaVariantRole
    let status: String
    let mimeType: String
    let byteSize: Int64
    let contentPath: String

    enum CodingKeys: String, CodingKey {
        case id, role, status
        case mimeType = "mime_type"
        case byteSize = "byte_size"
        case contentPath = "content_url"
    }
}

enum VideoPlaybackRepresentation: Equatable, Sendable {
    case ordinary
    case spatial(variantID: UUID)

    var isSpatial: Bool {
        if case .spatial = self {
            return true
        }
        return false
    }
}

struct VideoPlaybackSource: Equatable, Sendable {
    let path: String
    let mimeType: String?
    let byteSize: Int64
    let representation: VideoPlaybackRepresentation
}

struct XRMediaDetail: Decodable, Hashable, Identifiable, Sendable {
    let id: UUID
    let kind: MediaKind
    let status: String
    let mimeType: String?
    let width: Int?
    let height: Int?
    let durationSeconds: Double?
    let byteSize: Int64
    let isTrash: Bool
    let previewPath: String
    let playbackPath: String
    let originalPath: String
    let spatialAvailable: Bool
    let variants: [XRMediaVariant]
    var prefersSpatialPlayback: Bool
    var favorite: Bool

    enum CodingKeys: String, CodingKey {
        case id, kind, status, width, height
        case mimeType = "mime_type"
        case durationSeconds = "duration_seconds"
        case byteSize = "byte_size"
        case isTrash = "is_trash"
        case previewPath = "preview_url"
        case playbackPath = "playback_url"
        case originalPath = "original_url"
        case spatialAvailable = "spatial_available"
        case prefersSpatialPlayback = "prefer_spatial_playback"
        case legacySpatialViewPreferred = "spatial_view_preferred"
        case variants
        case favorite
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        kind = try container.decode(MediaKind.self, forKey: .kind)
        status = try container.decode(String.self, forKey: .status)
        mimeType = try container.decodeIfPresent(String.self, forKey: .mimeType)
        width = try container.decodeIfPresent(Int.self, forKey: .width)
        height = try container.decodeIfPresent(Int.self, forKey: .height)
        durationSeconds = try container.decodeIfPresent(Double.self, forKey: .durationSeconds)
        byteSize = try container.decode(Int64.self, forKey: .byteSize)
        isTrash = try container.decode(Bool.self, forKey: .isTrash)
        previewPath = try container.decode(String.self, forKey: .previewPath)
        playbackPath = try container.decode(String.self, forKey: .playbackPath)
        originalPath = try container.decode(String.self, forKey: .originalPath)
        spatialAvailable = try container.decodeIfPresent(Bool.self, forKey: .spatialAvailable) ?? false
        variants = try container.decodeIfPresent([XRMediaVariant].self, forKey: .variants) ?? []
        prefersSpatialPlayback =
            try container.decodeIfPresent(Bool.self, forKey: .prefersSpatialPlayback)
            ?? container.decodeIfPresent(Bool.self, forKey: .legacySpatialViewPreferred)
            ?? false
        favorite = try container.decodeIfPresent(Bool.self, forKey: .favorite) ?? false
    }

    init(summary: XRMediaSummary) {
        id = summary.id
        kind = summary.kind
        status = summary.status
        mimeType = summary.mimeType
        width = summary.width
        height = summary.height
        durationSeconds = summary.durationSeconds
        byteSize = summary.byteSize
        isTrash = summary.isTrash
        previewPath = summary.previewPath
        playbackPath = "/api/v1/media/\(summary.id.uuidString.lowercased())/playback"
        originalPath = "/api/v1/media/\(summary.id.uuidString.lowercased())/original"
        spatialAvailable = summary.spatialAvailable
        variants = []
        prefersSpatialPlayback = summary.prefersSpatialPlayback
        favorite = summary.favorite
    }

    var preferences: MediaPreferences {
        get {
            MediaPreferences(
                favorite: favorite,
                prefersSpatialPlayback: prefersSpatialPlayback
            )
        }
        set {
            favorite = newValue.favorite
            prefersSpatialPlayback = newValue.prefersSpatialPlayback
        }
    }

    var activeSpatialVideoVariant: XRMediaVariant? {
        guard kind == .video, spatialAvailable else { return nil }
        return variants.first {
            $0.role == .spatialVideo
                && $0.status == "ready"
                && !$0.contentPath.isEmpty
        }
    }

    var selectedVideoPlaybackSource: VideoPlaybackSource? {
        guard kind == .video else { return nil }
        if prefersSpatialPlayback, let variant = activeSpatialVideoVariant {
            return VideoPlaybackSource(
                path: variant.contentPath,
                mimeType: variant.mimeType,
                byteSize: variant.byteSize,
                representation: .spatial(variantID: variant.id)
            )
        }
        return VideoPlaybackSource(
            path: playbackPath,
            mimeType: mimeType,
            byteSize: byteSize,
            representation: .ordinary
        )
    }
}

struct MediaPlaybackPreferenceResponse: Decodable, Sendable {
    let mediaID: UUID
    let prefersSpatialPlayback: Bool

    enum CodingKeys: String, CodingKey {
        case mediaID = "media_id"
        case prefersSpatialPlayback = "prefer_spatial_playback"
        case legacySpatialViewPreferred = "spatial_view_preferred"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        mediaID = try container.decode(UUID.self, forKey: .mediaID)
        prefersSpatialPlayback =
            try container.decodeIfPresent(Bool.self, forKey: .prefersSpatialPlayback)
            ?? container.decode(Bool.self, forKey: .legacySpatialViewPreferred)
    }
}

struct MediaFavoriteResponse: Decodable, Sendable {
    let mediaID: UUID
    let favorite: Bool

    enum CodingKeys: String, CodingKey {
        case mediaID = "media_id"
        case favorite
    }
}

struct MediaNavigation: Decodable, Hashable, Sendable {
    let mediaID: UUID
    let position: Int
    let total: Int
    let previousID: UUID?
    let previousPosition: Int?
    let nextID: UUID?
    let nextPosition: Int?

    enum CodingKeys: String, CodingKey {
        case mediaID = "media_id"
        case position, total
        case previousID = "previous_id"
        case previousPosition = "previous_position"
        case nextID = "next_id"
        case nextPosition = "next_position"
    }
}

struct ViewerSelection: Codable, Hashable, Sendable {
    let mediaID: UUID
    let scope: GalleryScope
}

enum SpatialGenerationState: Equatable, Sendable {
    case unavailable
    case ready2D
    case generating
    case spatial
    case failed(String)
}

enum SpatialEligibility: Equatable, Sendable {
    case eligible
    case unavailable(String)

    static func evaluate(kind: MediaKind, width: Int?, height: Int?) -> Self {
        guard kind == .image else {
            return .unavailable("Spatial generation is available for images only.")
        }
        guard let width, let height else {
            return .unavailable("Image dimensions are unavailable.")
        }
        let shortest = min(width, height)
        let longest = max(width, height)
        guard shortest >= 320 else {
            return .unavailable("The shortest side must be at least 320 pixels.")
        }
        guard longest <= 16_384 else {
            return .unavailable("The longest side must be 16,384 pixels or less.")
        }
        let ratio = Double(width) / Double(height)
        guard (1.0 / 3.0)...3.0 ~= ratio else {
            return .unavailable("The aspect ratio must be between 1:3 and 3:1.")
        }
        return .eligible
    }
}

struct APIErrorEnvelope: Decodable, Sendable {
    struct Body: Decodable, Sendable {
        let code: String
        let message: String
        let requestID: String?

        enum CodingKeys: String, CodingKey {
            case code, message
            case requestID = "request_id"
        }
    }

    let error: Body
}
