# Project Comfy Gallery iOS App — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete native SwiftUI iOS app (M0–M4) for browsing media and performing blind reviews against a self-hosted Project Comfy Gallery backend.

**Architecture:** Unidirectional feature pattern with `@Observable` feature models on `@MainActor`, actor-based services (`APIClient`, `MediaRepository`, `ReviewCommandQueue`), SwiftData for disposable client state, Keychain for credentials. SwiftUI adaptive layouts for iPhone/iPad.

**Tech Stack:** Swift 6, SwiftUI, async/await, URLSession, AVKit, SwiftData, Keychain Services, ImageIO, OSLog, XCTest, XCUITest

---

### Task 1: Create Xcode project structure

**Files:**
- Create: `mobile/ComfyGalleryMobile.xcodeproj` (via `xcodebuild` or manual)
- Create: `mobile/Config/Debug.xcconfig`
- Create: `mobile/Config/Release.xcconfig`

**Step 1: Create the project with Swift Package Manager as a skeleton, then convert**

Since we can't run Xcode interactively, create the project using `swift package init` and then hand-craft the `.xcodeproj`. Actually, the most reliable approach for CLI generation is to create all Swift source files and an `project.yml` for XcodeGen, or to use `xcodebuild` with a template.

Run: `which xcodegen || which xcodebuild`

If `xcodegen` is not available, we'll create the `.xcodeproj` structure manually using `xcodeproj` Ruby gem or write the `project.pbxproj` directly.

**Step 2: Create Config files**

Create `mobile/Config/Debug.xcconfig`:
```
SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG
SWIFT_OPTIMIZATION_LEVEL = -Onone
BUNDLE_ID_SUFFIX = .debug
```

Create `mobile/Config/Release.xcconfig`:
```
SWIFT_ACTIVE_COMPILATION_CONDITIONS = RELEASE
SWIFT_OPTIMIZATION_LEVEL = -O
BUNDLE_ID_SUFFIX = 
```

**Step 3: Create directory structure**

Run:
```bash
mkdir -p mobile/ComfyGalleryMobile/{App,Core/{API/Models,Auth,Media,Persistance,Support},Features/{Connection,Library,Viewer,ReviewHome,ReviewWorkspace,Settings},DesignSystem,Resources,PreviewContent}
mkdir -p mobile/ComfyGalleryMobileTests
mkdir -p mobile/ComfyGalleryMobileUITests
mkdir -p mobile/Fixtures
```

**Step 4: Create Info.plist**

Create `mobile/ComfyGalleryMobile/Resources/Info.plist` with:
- `NSLocalNetworkUsageDescription` = "Connect to your self-hosted Comfy Gallery server on the local network."
- `UISupportedInterfaceOrientations` for iPhone (portrait, landscape) and iPad (all)

**Step 5: Create Assets.xcassets**

Create `mobile/ComfyGalleryMobile/Resources/Assets.xcassets/Contents.json` with a basic empty asset catalog structure.

**Step 6: Create the Xcode project using xcodegen spec**

Create `mobile/project.yml` for XcodeGen with:
- Target: ComfyGalleryMobile (iOS 17.0, Swift 6)
- Target: ComfyGalleryMobileTests
- Target: ComfyGalleryMobileUITests
- Config files: Debug.xcconfig, Release.xcconfig
- All source files included
- Framework dependencies: none (pure Apple SDK)

Run: `cd mobile && xcodegen generate` (if xcodegen available)

If xcodegen is not available, create a minimal `project.pbxproj` manually.

---

### Task 2: App entry point and environment

**Files:**
- Create: `mobile/ComfyGalleryMobile/App/ComfyGalleryMobileApp.swift`
- Create: `mobile/ComfyGalleryMobile/App/AppEnvironment.swift`
- Create: `mobile/ComfyGalleryMobile/App/RootView.swift`

**Step 1: Write ComfyGalleryMobileApp.swift**

```swift
import SwiftUI
import OSLog

@main
struct ComfyGalleryMobileApp: App {
    @State private var environment = AppEnvironment()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
                .onChange(of: scenePhase) { _, newPhase in
                    environment.handleScenePhase(newPhase)
                }
        }
        .onChange(of: scenePhase) { _, newPhase in
            environment.handleScenePhase(newPhase)
        }
    }

    @Environment(\.scenePhase) private var scenePhase
}
```

**Step 2: Write AppEnvironment.swift**

```swift
import SwiftUI
import OSLog
import SwiftData

@MainActor
@Observable
final class AppEnvironment {
    let apiClient: APIClient
    let connectionService: ConnectionService
    let mediaRepository: MediaRepository
    let reviewCommandQueue: ReviewCommandQueue
    let localStore: LocalStore

    var selectedTab: Tab = .library
    var isConnected = false
    var activeReviewSessionID: String?

    enum Tab: String, Codable {
        case library, review, settings
    }

    init() {
        let store = LocalStore()
        self.localStore = store
        self.apiClient = APIClient(credentialStore: CredentialStore())
        self.connectionService = ConnectionService(
            apiClient: apiClient,
            credentialStore: CredentialStore(),
            localStore: store
        )
        self.mediaRepository = MediaRepository(apiClient: apiClient)
        self.reviewCommandQueue = ReviewCommandQueue(
            apiClient: apiClient,
            localStore: store
        )
    }

    init(
        apiClient: APIClient,
        connectionService: ConnectionService,
        mediaRepository: MediaRepository,
        reviewCommandQueue: ReviewCommandQueue,
        localStore: LocalStore
    ) {
        self.apiClient = apiClient
        self.connectionService = connectionService
        self.mediaRepository = mediaRepository
        self.reviewCommandQueue = reviewCommandQueue
        self.localStore = localStore
    }

    func handleScenePhase(_ phase: ScenePhase) {
        switch phase {
        case .active:
            Task { await restoreAndReconcile() }
        case .inactive, .background:
            Task { await flushPendingCommands() }
        @unknown default:
            break
        }
    }

    private func restoreAndReconcile() async {
        // Validate auth, reconcile pending, fetch visible item, restart prefetch
    }

    private func flushPendingCommands() async {
        // Bounded best-effort command flush
    }
}
```

**Step 3: Write RootView.swift**

```swift
import SwiftUI

struct RootView: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        Group {
            if environment.isConnected {
                TabView(selection: Bindable(environment).selectedTab) {
                    LibraryView()
                        .tabItem { Label("Library", systemImage: "photo.on.rectangle") }
                        .tag(AppEnvironment.Tab.library)

                    ReviewHomeView()
                        .tabItem { Label("Review", systemImage: "checklist") }
                        .tag(AppEnvironment.Tab.review)

                    SettingsView()
                        .tabItem { Label("Settings", systemImage: "gear") }
                        .tag(AppEnvironment.Tab.settings)
                }
            } else {
                ConnectionView()
            }
        }
    }
}
```

---

### Task 3: API models (DTOs)

**Files:**
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/Health.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/UserSession.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/MediaPage.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/ReviewSummary.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/ReviewSession.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/ReviewItem.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/Evaluation.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/APIErrorEnvelope.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Models/Enums.swift`

**Step 1: Write Health.swift**

```swift
import Foundation

struct Health: Decodable, Sendable {
    let status: String
    let service: String?
    let version: String?
    let checks: [String: String]?
}
```

**Step 2: Write UserSession.swift**

```swift
import Foundation

struct UserSession: Decodable, Sendable {
    let user: UserInfo

    struct UserInfo: Decodable, Sendable {
        let id: String
        let username: String
    }
}
```

**Step 3: Write MediaPage.swift**

```swift
import Foundation

struct MediaPage: Decodable, Sendable {
    let items: [MobileMediaSummary]
    let total: Int
    let limit: Int
    let offset: Int
}

struct MobileMediaSummary: Decodable, Identifiable, Sendable {
    let id: String
    let kind: MediaKind
    let evaluationState: EvaluationState?
    let isTrash: Bool?
    let previewURL: String

    enum CodingKeys: String, CodingKey {
        case id, kind
        case evaluationState = "evaluation_state"
        case isTrash = "is_trash"
        case previewURL = "preview_url"
    }
}
```

**Step 4: Write ReviewSummary.swift**

```swift
import Foundation

struct ReviewSummary: Decodable, Sendable {
    let notStartedCount: Int
    let inProgressCount: Int
    let completeCount: Int
    let trashCount: Int
    let activeSessionCount: Int

    enum CodingKeys: String, CodingKey {
        case notStartedCount = "not_started_count"
        case inProgressCount = "in_progress_count"
        case completeCount = "complete_count"
        case trashCount = "trash_count"
        case activeSessionCount = "active_session_count"
    }
}
```

**Step 5: Write ReviewSession.swift**

```swift
import Foundation

struct ReviewSession: Decodable, Identifiable, Sendable {
    let id: String
    let name: String?
    let sourceKind: SourceKind
    let orderingMode: OrderingMode
    let status: SessionStatus
    let currentCursor: Int?
    let candidateCount: Int
    let progressCounts: ProgressCounts?
    let optionalModules: [String]
    let lastOpenedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, name, status
        case sourceKind = "source_kind"
        case orderingMode = "ordering_mode"
        case currentCursor = "current_cursor"
        case candidateCount = "candidate_count"
        case progressCounts = "progress_counts"
        case optionalModules = "optional_modules"
        case lastOpenedAt = "last_opened_at"
    }
}

struct ProgressCounts: Decodable, Sendable {
    let notStarted: Int
    let inProgress: Int
    let complete: Int
    let trash: Int

    enum CodingKeys: String, CodingKey {
        case notStarted = "not_started"
        case inProgress = "in_progress"
        case complete, trash
    }
}

struct CreateSessionRequest: Encodable, Sendable {
    let name: String?
    let sourceKind: SourceKind
    let filter: MediaFilter?
    let randomLimit: Int
    let orderingMode: OrderingMode
    let optionalModules: [String]

    enum CodingKeys: String, CodingKey {
        case name, filter
        case sourceKind = "source_kind"
        case randomLimit = "random_limit"
        case orderingMode = "ordering_mode"
        case optionalModules = "optional_modules"
    }
}

struct MediaFilter: Encodable, Sendable {
    let kind: MediaKind?
    let evaluationState: EvaluationState?
    let trash: Bool?

    enum CodingKeys: String, CodingKey {
        case kind
        case evaluationState = "evaluation_state"
        case trash
    }
}

struct PatchSessionBody: Encodable, Sendable {
    let currentCursor: Int?
    let status: SessionStatus?

    enum CodingKeys: String, CodingKey {
        case currentCursor = "current_cursor"
        case status
    }
}
```

**Step 6: Write ReviewItem.swift**

```swift
import Foundation

struct ReviewItem: Decodable, Sendable {
    let session: ReviewItemSession
    let position: Int
    let media: ReviewMedia
    let prompts: [ReviewPrompt]
    let evaluations: [Evaluation]
}

struct ReviewItemSession: Decodable, Sendable {
    let id: String
    let currentCursor: Int?
    let candidateCount: Int
    let progressCounts: ProgressCounts?

    enum CodingKeys: String, CodingKey {
        case id
        case currentCursor = "current_cursor"
        case candidateCount = "candidate_count"
        case progressCounts = "progress_counts"
    }
}

struct ReviewMedia: Decodable, Sendable {
    let id: String
    let kind: MediaKind
    let previewURL: String
    let playbackURL: String?
    let width: Int?
    let height: Int?
    let durationSeconds: Double?

    enum CodingKeys: String, CodingKey {
        case id, kind, width, height
        case previewURL = "preview_url"
        case playbackURL = "playback_url"
        case durationSeconds = "duration_seconds"
    }
}

struct ReviewPrompt: Decodable, Identifiable, Sendable {
    let role: String
    let label: String
    let text: String

    var id: String { "\(role)-\(label)" }
}
```

**Step 7: Write Evaluation.swift**

```swift
import Foundation

struct Evaluation: Decodable, Identifiable, Sendable {
    let id: String
    let evaluationKind: String
    let progressState: ProgressState
    let isTrash: Bool
    let version: Int
    let criteria: [Criterion]
    let scores: [EvaluationScore]

    enum CodingKeys: String, CodingKey {
        case id, version, criteria, scores
        case evaluationKind = "evaluation_kind"
        case progressState = "progress_state"
        case isTrash = "is_trash"
    }
}

struct Criterion: Decodable, Identifiable, Sendable {
    let id: String
    let label: String
    let description: String?
    let minValue: Int?
    let maxValue: Int?

    enum CodingKeys: String, CodingKey {
        case id, label, description
        case minValue = "min_value"
        case maxValue = "max_value"
    }
}

struct EvaluationScore: Decodable, Sendable {
    let criterionVersionId: String
    let state: ScoreState
    let value: Int?
    let naReason: String?

    enum CodingKeys: String, CodingKey {
        case state, value
        case criterionVersionId = "criterion_version_id"
        case naReason = "na_reason"
    }
}

struct SetScoreRequest: Encodable, Sendable {
    let expectedVersion: Int
    let state: ScoreState
    let value: Int?
    let naReason: String?

    enum CodingKeys: String, CodingKey {
        case state, value
        case expectedVersion = "expected_version"
        case naReason = "na_reason"
    }
}

struct DeleteScoreRequest: Encodable, Sendable {
    let expectedVersion: Int

    enum CodingKeys: String, CodingKey {
        case expectedVersion = "expected_version"
    }
}

struct TrashRestoreRequest: Encodable, Sendable {
    let expectedVersion: Int

    enum CodingKeys: String, CodingKey {
        case expectedVersion = "expected_version"
    }
}
```

**Step 8: Write APIErrorEnvelope.swift**

```swift
import Foundation

struct APIErrorEnvelope: Decodable, Sendable {
    let error: APIErrorDetail

    struct APIErrorDetail: Decodable, Sendable {
        let code: String
        let message: String
        let details: [String: String]?
        let requestId: String?

        enum CodingKeys: String, CodingKey {
            case code, message, details
            case requestId = "request_id"
        }
    }
}

enum APIError: Error {
    case unauthorized
    case forbidden
    case notFound
    case conflict(APIErrorEnvelope)
    case validationError(APIErrorEnvelope)
    case rateLimited
    case serverError(Int)
    case networkError(Error)
    case decodingError(Error)
    case invalidURL
    case unknown(Int, APIErrorEnvelope?)
}
```

**Step 9: Write Enums.swift**

```swift
import Foundation

enum MediaKind: String, Decodable, Sendable {
    case image, video
}

enum EvaluationState: String, Decodable, Sendable {
    case notStarted = "not_started"
    case inProgress = "in_progress"
    case complete
}

enum ProgressState: String, Decodable, Sendable {
    case notStarted = "not_started"
    case inProgress = "in_progress"
    case complete
}

enum SessionStatus: String, Codable, Sendable {
    case active, finished, abandoned
}

enum SourceKind: String, Codable, Sendable {
    case random, inProgress = "in_progress"
    case filter
}

enum OrderingMode: String, Codable, Sendable {
    case random, stable
}

enum ScoreState: String, Codable, Sendable {
    case unset, scored, na
}

enum CommandKind: String, Codable, Sendable {
    case score, na, clear, trash, restore
}
```

---

### Task 4: API client and endpoint definitions

**Files:**
- Create: `mobile/ComfyGalleryMobile/Core/API/APIError.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/Endpoint.swift`
- Create: `mobile/ComfyGalleryMobile/Core/API/APIClient.swift`

**Step 1: Write APIError.swift**

```swift
import Foundation

enum APIError: Error, LocalizedError {
    case unauthorized
    case forbidden
    case notFound
    case conflict(APIErrorEnvelope)
    case validationError(APIErrorEnvelope)
    case rateLimited
    case serverError(Int)
    case networkError(Error)
    case decodingError(Error)
    case invalidURL
    case invalidResponse
    case unknown(Int, APIErrorEnvelope?)

    var errorDescription: String? {
        switch self {
        case .unauthorized:
            return "Authentication failed. Please reconnect."
        case .forbidden:
            return "Access denied. Check your token permissions."
        case .notFound:
            return "The requested resource was not found."
        case .conflict(let envelope):
            return envelope.error.message
        case .validationError(let envelope):
            return envelope.error.message
        case .rateLimited:
            return "Too many requests. Please wait."
        case .serverError(let code):
            return "Server error (\(code)). Please try again."
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .decodingError:
            return "Unexpected server response format."
        case .invalidURL:
            return "Invalid server URL."
        case .invalidResponse:
            return "Invalid server response."
        case .unknown(let code, _):
            return "Unexpected error (\(code))."
        }
    }

    var requestID: String? {
        switch self {
        case .conflict(let e): return e.error.requestId
        case .validationError(let e): return e.error.requestId
        case .unknown(_, let e): return e?.error.requestId
        default: return nil
        }
    }

    var isRetryable: Bool {
        switch self {
        case .serverError, .networkError, .rateLimited:
            return true
        case .unauthorized, .forbidden, .notFound, .conflict,
             .validationError, .invalidURL, .invalidResponse, .decodingError, .unknown:
            return false
        }
    }

    var requiresReauthentication: Bool {
        switch self {
        case .unauthorized, .forbidden: return true
        default: return false
        }
    }

    static func map(statusCode: Int, envelope: APIErrorEnvelope?) -> APIError {
        switch statusCode {
        case 401: return .unauthorized
        case 403: return .forbidden
        case 404: return .notFound
        case 409: return .conflict(envelope ?? APIErrorEnvelope(error: .init(code: "UNKNOWN", message: "Conflict", details: nil, requestId: nil)))
        case 422: return .validationError(envelope ?? APIErrorEnvelope(error: .init(code: "UNKNOWN", message: "Validation error", details: nil, requestId: nil)))
        case 429: return .rateLimited
        case 500...599: return .serverError(statusCode)
        default: return .unknown(statusCode, envelope)
        }
    }
}
```

**Step 2: Write Endpoint.swift**

```swift
import Foundation

enum Endpoint {
    case health
    case authSession
    case mediaList(kind: MediaKind?, evaluationState: EvaluationState?, trash: Bool?, sort: String?, limit: Int, offset: Int)
    case mediaPreview(id: String)
    case mediaPlayback(id: String)
    case reviewSummary
    case reviewSessions(limit: Int?)
    case createReviewSession(CreateSessionRequest)
    case getReviewSession(id: String)
    case patchReviewSession(id: String, PatchSessionBody)
    case deleteReviewSession(id: String)
    case reviewItem(sessionID: String, position: Int)
    case setScore(evaluationID: String, criterionVersionID: String, SetScoreRequest)
    case deleteScore(evaluationID: String, criterionVersionID: String, DeleteScoreRequest)
    case trash(evaluationID: String, TrashRestoreRequest)
    case restore(evaluationID: String, TrashRestoreRequest)

    var path: String {
        switch self {
        case .health: return "/health/live"
        case .authSession: return "/api/v1/auth/session"
        case .mediaList: return "/api/v1/media"
        case .mediaPreview(let id): return "/api/v1/media/\(id)/preview"
        case .mediaPlayback(let id): return "/api/v1/media/\(id)/playback"
        case .reviewSummary: return "/api/v1/review/summary"
        case .reviewSessions: return "/api/v1/review-sessions"
        case .createReviewSession: return "/api/v1/review-sessions"
        case .getReviewSession(let id): return "/api/v1/review-sessions/\(id)"
        case .patchReviewSession(let id, _): return "/api/v1/review-sessions/\(id)"
        case .deleteReviewSession(let id): return "/api/v1/review-sessions/\(id)"
        case .reviewItem(let sessionID, let position): return "/api/v1/review-sessions/\(sessionID)/items/\(position)"
        case .setScore(let evaluationID, let criterionVersionID, _): return "/api/v1/evaluations/\(evaluationID)/scores/\(criterionVersionID)"
        case .deleteScore(let evaluationID, let criterionVersionID, _): return "/api/v1/evaluations/\(evaluationID)/scores/\(criterionVersionID)"
        case .trash(let evaluationID, _): return "/api/v1/evaluations/\(evaluationID)/trash"
        case .restore(let evaluationID, _): return "/api/v1/evaluations/\(evaluationID)/restore"
        }
    }

    var method: String {
        switch self {
        case .health, .authSession, .mediaList, .mediaPreview, .mediaPlayback,
             .reviewSummary, .reviewSessions, .getReviewSession, .reviewItem:
            return "GET"
        case .createReviewSession, .trash, .restore:
            return "POST"
        case .patchReviewSession:
            return "PATCH"
        case .setScore:
            return "PUT"
        case .deleteScore, .deleteReviewSession:
            return "DELETE"
        }
    }

    var requiresAuth: Bool {
        switch self {
        case .health: return false
        default: return true
        }
    }

    var queryItems: [URLQueryItem]? {
        switch self {
        case .mediaList(let kind, let evaluationState, let trash, let sort, let limit, let offset):
            var items: [URLQueryItem] = [
                URLQueryItem(name: "limit", value: String(limit)),
                URLQueryItem(name: "offset", value: String(offset)),
            ]
            if let kind = kind { items.append(URLQueryItem(name: "kind", value: kind.rawValue)) }
            if let state = evaluationState { items.append(URLQueryItem(name: "evaluation_state", value: state.rawValue)) }
            if let trash = trash { items.append(URLQueryItem(name: "trash", value: String(trash))) }
            if let sort = sort { items.append(URLQueryItem(name: "sort", value: sort)) }
            return items
        case .reviewSessions(let limit):
            if let limit = limit {
                return [URLQueryItem(name: "limit", value: String(limit))]
            }
            return nil
        default:
            return nil
        }
    }

    var body: Data? {
        let encoder = JSONEncoder()
        switch self {
        case .createReviewSession(let req):
            return try? encoder.encode(req)
        case .patchReviewSession(_, let body):
            return try? encoder.encode(body)
        case .setScore(_, _, let req):
            return try? encoder.encode(req)
        case .deleteScore(_, _, let req):
            return try? encoder.encode(req)
        case .trash(_, let req), .restore(_, let req):
            return try? encoder.encode(req)
        default:
            return nil
        }
    }

    var responseKind: ResponseKind {
        switch self {
        case .mediaPreview, .mediaPlayback:
            return .data
        case .health:
            return .json
        default:
            return .json
        }
    }

    enum ResponseKind {
        case json, data
    }
}
```

**Step 3: Write APIClient.swift**

```swift
import Foundation
import OSLog

actor APIClient {
    private let credentialStore: CredentialStore
    private let session: URLSession
    private var baseURL: URL?
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "APIClient")

    init(credentialStore: CredentialStore) {
        self.credentialStore = credentialStore
        let config = URLSessionConfiguration.ephemeral
        config.waitsForConnectivity = true
        config.timeoutIntervalForConnect = 10
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)
    }

    func configure(baseURL: URL) {
        self.baseURL = baseURL
    }

    func reset() {
        baseURL = nil
    }

    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let data: Data = try await performRequest(endpoint, responseKind: .json)
        let decoder = JSONDecoder()
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            logger.error("Decoding error for \(endpoint.path): \(error.localizedDescription)")
            throw APIError.decodingError(error)
        }
    }

    func requestData(_ endpoint: Endpoint) async throws -> Data {
        return try await performRequest(endpoint, responseKind: .data)
    }

    func download(_ endpoint: Endpoint, to destination: URL) async throws {
        let request = try buildRequest(for: endpoint)
        let (tempURL, response) = try await session.download(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        try validateResponse(httpResponse, data: Data())
        try FileManager.default.moveItem(at: tempURL, to: destination)
    }

    private func performRequest(_ endpoint: Endpoint, responseKind: Endpoint.ResponseKind) async throws -> Data {
        let request = try buildRequest(for: endpoint)
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        try validateResponse(httpResponse, data: data)
        return data
    }

    private func buildRequest(for endpoint: Endpoint) throws -> URLRequest {
        guard let baseURL = baseURL else {
            throw APIError.invalidURL
        }
        guard var components = URLComponents(url: baseURL.appendingPathComponent(endpoint.path), resolvingAgainstBaseURL: true) else {
            throw APIError.invalidURL
        }
        if let queryItems = endpoint.queryItems {
            components.queryItems = queryItems
        }
        guard let url = components.url, url.host == baseURL.host else {
            throw APIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if endpoint.requiresAuth, let token = await credentialStore.token() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body = endpoint.body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return request
    }

    private func validateResponse(_ response: HTTPURLResponse, data: Data) throws {
        guard (200...299).contains(response.statusCode) else {
            var envelope: APIErrorEnvelope?
            if let decoded = try? JSONDecoder().decode(APIErrorEnvelope.self, from: data) {
                envelope = decoded
            }
            throw APIError.map(statusCode: response.statusCode, envelope: envelope)
        }
    }
}
```

---

### Task 5: Authentication (Keychain + ConnectionService)

**Files:**
- Create: `mobile/ComfyGalleryMobile/Core/Auth/CredentialStore.swift`
- Create: `mobile/ComfyGalleryMobile/Core/Auth/ConnectionService.swift`

**Step 1: Write CredentialStore.swift**

```swift
import Foundation
import Security
import OSLog

final class CredentialStore: Sendable {
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "CredentialStore")
    private let service = "com.comfygallery.mobile.token"

    func store(token: String, for profileID: String) {
        delete(for: profileID)
        let account = profileID
        guard let data = token.data(using: .utf8) else { return }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let status = SecItemAdd(query as CFDictionary, nil)
        if status != errSecSuccess {
            logger.error("Keychain store failed: \(status)")
        }
    }

    func token(for profileID: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: profileID,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            return nil
        }
        return token
    }

    func token() async -> String? {
        // Default profile for V1: use first stored token
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            return nil
        }
        return token
    }

    func delete(for profileID: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: profileID,
        ]
        SecItemDelete(query as CFDictionary)
    }

    func deleteAll() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
```

**Step 2: Write ConnectionService.swift**

```swift
import Foundation
import OSLog

@MainActor
@Observable
final class ConnectionService {
    private let apiClient: APIClient
    private let credentialStore: CredentialStore
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "Connection")

    var connectionState: ConnectionState = .disconnected
    var serverVersion: String?
    var baseURL: URL?

    enum ConnectionState: Equatable {
        case disconnected
        case checkingServer
        case serverFound
        case authenticationRequired
        case authenticating
        case connected(UserSession)
        case error(String)
    }

    init(apiClient: APIClient, credentialStore: CredentialStore, localStore: LocalStore) {
        self.apiClient = apiClient
        self.credentialStore = credentialStore
        self.localStore = localStore
    }

    func connect(urlString: String, token: String? = nil) async {
        connectionState = .checkingServer

        guard let normalized = normalizeURL(urlString) else {
            connectionState = .error("Invalid URL. Enter a server address like http://192.168.50.68:8181")
            return
        }
        self.baseURL = normalized
        await apiClient.configure(baseURL: normalized)

        do {
            let health: Health = try await apiClient.request(.health)
            connectionState = .serverFound
            serverVersion = health.version
        } catch {
            connectionState = .error("Could not reach server. Check the address and ensure the server is running.")
            return
        }

        let tokenToUse: String
        if let token = token {
            tokenToUse = token
        } else if let saved = await credentialStore.token() {
            tokenToUse = saved
        } else {
            connectionState = .authenticationRequired
            return
        }

        await authenticate(token: tokenToUse)
    }

    func authenticate(token: String) async {
        connectionState = .authenticating
        do {
            let session: UserSession = try await apiClient.request(.authSession)
            await credentialStore.store(token: token, for: session.user.id)
            connectionState = .connected(session)
        } catch {
            connectionState = .error("Authentication failed. Check your API token.")
        }
    }

    func disconnect() async {
        await credentialStore.deleteAll()
        await apiClient.reset()
        try? await localStore.clearAll()
        baseURL = nil
        serverVersion = nil
        connectionState = .disconnected
    }

    private func normalizeURL(_ urlString: String) -> URL? {
        var string = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        if !string.hasPrefix("http://") && !string.hasPrefix("https://") {
            string = "http://\(string)"
        }
        guard let url = URL(string: string),
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.host != nil else {
            return nil
        }
        var normalized = components
        if !normalized.path.isEmpty && normalized.path != "/" {
            // Keep explicit path prefix
        }
        return normalized.url
    }
}
```

---

### Task 6: SwiftData persistence

**Files:**
- Create: `mobile/ComfyGalleryMobile/Core/Persistence/LocalStore.swift`
- Create: `mobile/ComfyGalleryMobile/Core/Persistence/PendingMutation.swift`

**Step 1: Write PendingMutation.swift**

```swift
import Foundation
import SwiftData

@Model
final class PendingMutation {
    var localUUID: String
    var serverProfileUUID: String
    var reviewSessionUUID: String
    var mediaUUID: String
    var evaluationUUID: String
    var criterionVersionUUID: String?
    var commandKindRaw: String
    var intendedValue: Int?
    var intendedState: String?
    var baseEvaluationVersion: Int
    var createdAt: Date
    var attemptCount: Int
    var lastErrorCategory: String?

    var commandKind: CommandKind {
        CommandKind(rawValue: commandKindRaw) ?? .score
    }

    init(
        localUUID: String = UUID().uuidString,
        serverProfileUUID: String,
        reviewSessionUUID: String,
        mediaUUID: String,
        evaluationUUID: String,
        criterionVersionUUID: String? = nil,
        commandKind: CommandKind,
        intendedValue: Int? = nil,
        intendedState: String? = nil,
        baseEvaluationVersion: Int,
        createdAt: Date = Date(),
        attemptCount: Int = 0,
        lastErrorCategory: String? = nil
    ) {
        self.localUUID = localUUID
        self.serverProfileUUID = serverProfileUUID
        self.reviewSessionUUID = reviewSessionUUID
        self.mediaUUID = mediaUUID
        self.evaluationUUID = evaluationUUID
        self.criterionVersionUUID = criterionVersionUUID
        self.commandKindRaw = commandKind.rawValue
        self.intendedValue = intendedValue
        self.intendedState = intendedState
        self.baseEvaluationVersion = baseEvaluationVersion
        self.createdAt = createdAt
        self.attemptCount = attemptCount
        self.lastErrorCategory = lastErrorCategory
    }
}

@Model
final class ServerProfile {
    var uuid: String
    var baseURL: String
    var displayName: String?
    var lastServerVersion: String?
    var lastConnectionDate: Date?
    var isActive: Bool

    init(
        uuid: String = UUID().uuidString,
        baseURL: String,
        displayName: String? = nil,
        lastServerVersion: String? = nil,
        lastConnectionDate: Date? = nil,
        isActive: Bool = true
    ) {
        self.uuid = uuid
        self.baseURL = baseURL
        self.displayName = displayName
        self.lastServerVersion = lastServerVersion
        self.lastConnectionDate = lastConnectionDate
        self.isActive = isActive
    }
}

@Model
final class CachedSessionSummary {
    var sessionUUID: String
    var name: String?
    var status: String
    var currentCursor: Int
    var candidateCount: Int
    var lastOpenedAt: Date?
    var sourceKind: String
    var serverProfileUUID: String

    init(
        sessionUUID: String,
        name: String? = nil,
        status: String,
        currentCursor: Int = 0,
        candidateCount: Int = 0,
        lastOpenedAt: Date? = nil,
        sourceKind: String,
        serverProfileUUID: String
    ) {
        self.sessionUUID = sessionUUID
        self.name = name
        self.status = status
        self.currentCursor = currentCursor
        self.candidateCount = candidateCount
        self.lastOpenedAt = lastOpenedAt
        self.sourceKind = sourceKind
        self.serverProfileUUID = serverProfileUUID
    }
}
```

**Step 2: Write LocalStore.swift**

```swift
import Foundation
import SwiftData
import OSLog

@MainActor
final class LocalStore {
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "LocalStore")
    let modelContainer: ModelContainer
    let modelContext: ModelContext

    init() {
        let schema = Schema([PendingMutation.self, ServerProfile.self, CachedSessionSummary.self])
        let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        do {
            self.modelContainer = try ModelContainer(for: schema, configurations: [config])
            self.modelContext = modelContainer.mainContext
        } catch {
            fatalError("Failed to create ModelContainer: \(error)")
        }
    }

    func activeProfile() throws -> ServerProfile? {
        var descriptor = FetchDescriptor<ServerProfile>(
            predicate: #Predicate { $0.isActive == true }
        )
        descriptor.fetchLimit = 1
        return try modelContext.fetch(descriptor).first
    }

    func saveProfile(_ profile: ServerProfile) throws {
        modelContext.insert(profile)
        try modelContext.save()
    }

    func pendingMutations(for evaluationUUID: String) throws -> [PendingMutation] {
        var descriptor = FetchDescriptor<PendingMutation>(
            predicate: #Predicate { $0.evaluationUUID == evaluationUUID },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        return try modelContext.fetch(descriptor)
    }

    func allPendingMutations() throws -> [PendingMutation] {
        let descriptor = FetchDescriptor<PendingMutation>(
            sortBy: [SortDescriptor(\.createdAt)]
        )
        return try modelContext.fetch(descriptor)
    }

    func insertPendingMutation(_ mutation: PendingMutation) throws {
        modelContext.insert(mutation)
        try modelContext.save()
    }

    func deletePendingMutation(_ mutation: PendingMutation) throws {
        modelContext.delete(mutation)
        try modelContext.save()
    }

    func clearAll() throws {
        try modelContext.delete(model: PendingMutation.self)
        try modelContext.delete(model: ServerProfile.self)
        try modelContext.delete(model: CachedSessionSummary.self)
        try modelContext.save()
    }

    func clearPendingMutations(for profileUUID: String) throws {
        let mutations = try modelContext.fetch(
            FetchDescriptor<PendingMutation>(
                predicate: #Predicate { $0.serverProfileUUID == profileUUID }
            )
        )
        for mutation in mutations {
            modelContext.delete(mutation)
        }
        try modelContext.save()
    }
}
```

---

### Task 7: Media pipeline (image decoder + video cache + repository)

**Files:**
- Create: `mobile/ComfyGalleryMobile/Core/Media/ImageDecoder.swift`
- Create: `mobile/ComfyGalleryMobile/Core/Media/VideoCache.swift`
- Create: `mobile/ComfyGalleryMobile/Core/Media/MediaRepository.swift`

**Step 1: Write ImageDecoder.swift**

```swift
import Foundation
import ImageIO
import UIKit

enum ImageDecoder {
    static func downsample(data: Data, to size: CGSize, scale: CGFloat = UIScreen.main.scale) -> UIImage? {
        let maxDimension = max(size.width, size.height) * scale
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: maxDimension,
            kCGImageSourceShouldCacheImmediately: true,
        ]
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let cgImage = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
            return nil
        }
        return UIImage(cgImage: cgImage)
    }
}
```

**Step 2: Write VideoCache.swift**

```swift
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
        loadIndex()
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
        // Remove partial file if it exists
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
            try? data.write(to: indexURL)
        }
    }
}
```

**Step 3: Write MediaRepository.swift**

```swift
import Foundation
import UIKit
import OSLog

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
        NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { await self?.handleMemoryWarning() }
        }
    }

    func fetchPreviewImage(mediaID: String, previewURL: String, targetSize: CGSize) async throws -> UIImage? {
        if let cached = imageCache.object(forKey: mediaID as NSString) {
            return cached
        }
        if let existing = activeTasks[mediaID] {
            let data = try await existing.value
            return ImageDecoder.downsample(data: data, to: targetSize)
        }
        let task = Task<Data, Error> {
            return try await apiClient.requestData(.mediaPreview(id: mediaID))
        }
        activeTasks[mediaID] = task
        defer { activeTasks[mediaID] = nil }

        let data = try await task.value
        guard let image = ImageDecoder.downsample(data: data, to: targetSize) else {
            throw APIError.invalidResponse
        }
        imageCache.setObject(image, forKey: mediaID as NSString)
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
                .appendingPathComponent("video_download_\(UUID().uuidString).mp4")
            try await apiClient.download(.mediaPlayback(id: mediaID), to: tempURL)
            let cachedURL = try await videoCache.store(mediaID: mediaID, sourceURL: tempURL)
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

    private func handleMemoryWarning() {
        imageCache.removeAllObjects()
    }
}
```

---

### Task 8: Review command queue

**Files:**
- Create: `mobile/ComfyGalleryMobile/Core/API/ReviewCommandQueue.swift`

**Step 1: Write ReviewCommandQueue.swift**

```swift
import Foundation
import OSLog

actor ReviewCommandQueue {
    private let apiClient: APIClient
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "CommandQueue")
    private var lanes: [String: Lane] = [:]
    private let maxRetries = 5
    private let baseBackoff: UInt64 = 500_000_000 // 500ms

    struct Lane {
        var commands: [PendingMutation] = []
        var isProcessing = false
    }

    init(apiClient: APIClient, localStore: LocalStore) {
        self.apiClient = apiClient
        self.localStore = localStore
    }

    func enqueue(_ mutation: PendingMutation) async {
        if lanes[mutation.evaluationUUID] == nil {
            lanes[mutation.evaluationUUID] = Lane()
        }
        lanes[mutation.evaluationUUID]?.commands.append(mutation)
        await processLane(evaluationUUID: mutation.evaluationUUID)
    }

    func reconcilePending(for evaluationUUID: String, currentVersion: Int) async -> Bool {
        // Fetch current item to see if intended state is already present
        // Returns true if all pending commands are reconciled
        guard let lane = lanes[evaluationUUID], !lane.commands.isEmpty else { return true }
        return false
    }

    private func processLane(evaluationUUID: String) async {
        guard var lane = lanes[evaluationUUID], !lane.isProcessing else { return }
        lane.isProcessing = true
        lanes[evaluationUUID] = lane

        defer {
            lanes[evaluationUUID]?.isProcessing = false
        }

        while let command = lanes[evaluationUUID]?.commands.first {
            do {
                try await execute(command)
                lanes[evaluationUUID]?.commands.removeFirst()
                try? await localStore.deletePendingMutation(command)
            } catch let error as APIError {
                await handleError(error, mutation: command)
                if !error.isRetryable { break }
            } catch {
                command.lastErrorCategory = "network"
                command.attemptCount += 1
                try? await localStore.modelContext.save()
                if command.attemptCount >= maxRetries { break }
                let backoff = baseBackoff * UInt64(pow(2.0, Double(command.attemptCount - 1)))
                let jitter = UInt64.random(in: 0...(backoff / 4))
                try? await Task.sleep(nanoseconds: backoff + jitter)
            }
        }
    }

    private func execute(_ mutation: PendingMutation) async throws {
        let endpoint: Endpoint
        switch mutation.commandKind {
        case .score:
            let request = SetScoreRequest(
                expectedVersion: mutation.baseEvaluationVersion,
                state: .scored,
                value: mutation.intendedValue,
                naReason: nil
            )
            endpoint = .setScore(
                evaluationID: mutation.evaluationUUID,
                criterionVersionID: mutation.criterionVersionUUID ?? "",
                request
            )
        case .na:
            let request = SetScoreRequest(
                expectedVersion: mutation.baseEvaluationVersion,
                state: .na,
                value: nil,
                naReason: nil
            )
            endpoint = .setScore(
                evaluationID: mutation.evaluationUUID,
                criterionVersionID: mutation.criterionVersionUUID ?? "",
                request
            )
        case .clear:
            let request = DeleteScoreRequest(expectedVersion: mutation.baseEvaluationVersion)
            endpoint = .deleteScore(
                evaluationID: mutation.evaluationUUID,
                criterionVersionID: mutation.criterionVersionUUID ?? "",
                request
            )
        case .trash:
            let request = TrashRestoreRequest(expectedVersion: mutation.baseEvaluationVersion)
            endpoint = .trash(evaluationID: mutation.evaluationUUID, request)
        case .restore:
            let request = TrashRestoreRequest(expectedVersion: mutation.baseEvaluationVersion)
            endpoint = .restore(evaluationID: mutation.evaluationUUID, request)
        }
        let _: Evaluation = try await apiClient.request(endpoint)
    }

    private func handleError(_ error: APIError, mutation: PendingMutation) async {
        mutation.attemptCount += 1
        mutation.lastErrorCategory = String(describing: error)
        try? await localStore.modelContext.save()

        if error.requiresReauthentication {
            lanes.removeAll()
        }
    }
}
```

---

### Task 9: Connection feature view

**Files:**
- Create: `mobile/ComfyGalleryMobile/Features/Connection/ConnectionView.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Connection/ConnectionFeature.swift`

**Step 1: Write ConnectionFeature.swift**

```swift
import SwiftUI
import OSLog

@MainActor
@Observable
final class ConnectionFeature {
    var serverURL: String = ""
    var apiToken: String = ""
    var isConnecting = false
    var errorMessage: String?
    var showHTTPWarning = false
    var pendingURL: String?

    private let connectionService: ConnectionService
    private let environment: AppEnvironment

    init(connectionService: ConnectionService, environment: AppEnvironment) {
        self.connectionService = connectionService
        self.environment = environment
    }

    func connect() async {
        guard !serverURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Enter a server address."
            return
        }
        isConnecting = true
        errorMessage = nil

        let trimmed = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasPrefix("http://") {
            showHTTPWarning = true
            pendingURL = trimmed
            isConnecting = false
            return
        }

        await performConnect(url: trimmed)
    }

    func confirmHTTP() async {
        showHTTPWarning = false
        guard let url = pendingURL else { return }
        isConnecting = true
        await performConnect(url: url)
    }

    func cancelHTTP() {
        showHTTPWarning = false
        pendingURL = nil
    }

    private func performConnect(url: String) async {
        let token = apiToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? nil
            : apiToken.trimmingCharacters(in: .whitespacesAndNewlines)

        await connectionService.connect(urlString: url, token: token)

        switch connectionService.connectionState {
        case .connected:
            // Let connection service handle state
            break
        case .authenticationRequired:
            // Token prompt
            break
        case .error(let message):
            errorMessage = message
        default:
            break
        }
        isConnecting = false
    }

    func pasteTokenAndConnect() async {
        guard let token = UIPasteboard.general.string?.trimmingCharacters(in: .whitespacesAndNewlines),
              !token.isEmpty else {
            errorMessage = "No token found in clipboard."
            return
        }
        apiToken = token
        await connect()
    }
}
```

**Step 2: Write ConnectionView.swift**

```swift
import SwiftUI

struct ConnectionView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: ConnectionFeature

    init() {
        _feature = State(initialValue: ConnectionFeature(
            connectionService: AppEnvironment().connectionService,
            environment: AppEnvironment()
        ))
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    Spacer().frame(height: 40)

                    // App mark
                    Image(systemName: "photo.on.rectangle.angled")
                        .font(.system(size: 60))
                        .foregroundStyle(.tint)
                        .padding(.bottom, 8)

                    Text("Comfy Gallery")
                        .font(.largeTitle)
                        .fontWeight(.bold)

                    Text("Connect to your self-hosted gallery server")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    VStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Server URL")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            TextField("http://192.168.50.68:8181", text: $feature.serverURL)
                                .textFieldStyle(.roundedBorder)
                                .keyboardType(.URL)
                                .autocapitalization(.none)
                                .disableAutocorrection(true)
                        }

                        VStack(alignment: .leading, spacing: 6) {
                            Text("API Token")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            SecureField("cgpat_...", text: $feature.apiToken)
                                .textFieldStyle(.roundedBorder)
                        }

                        Button {
                            Task { await feature.connect() }
                        } label: {
                            HStack {
                                if feature.isConnecting {
                                    ProgressView()
                                }
                                Text("Connect")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(feature.isConnecting)

                        Button {
                            Task { await feature.pasteTokenAndConnect() }
                        } label: {
                            Label("Paste API Token & Connect", systemImage: "doc.on.clipboard")
                        }
                        .buttonStyle(.bordered)
                    }

                    if let error = feature.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                            .multilineTextAlignment(.center)
                    }

                    // Connection state display
                    connectionStateView
                }
                .padding(.horizontal, 24)
            }
            .alert("Unencrypted Connection", isPresented: $feature.showHTTPWarning) {
                Button("Connect Anyway") {
                    Task { await feature.confirmHTTP() }
                }
                Button("Cancel", role: .cancel) {
                    feature.cancelHTTP()
                }
            } message: {
                Text("HTTP connections on your local network are not encrypted. Credentials and media may be visible to other devices on the same network.")
            }
        }
    }

    @ViewBuilder
    private var connectionStateView: some View {
        switch environment.connectionService.connectionState {
        case .checkingServer:
            HStack(spacing: 8) {
                ProgressView()
                Text("Checking server...")
            }
            .foregroundStyle(.secondary)
        case .serverFound:
            Label("Server found", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .authenticationRequired:
            Label("Authentication required", systemImage: "lock.fill")
                .foregroundStyle(.orange)
        case .authenticating:
            HStack(spacing: 8) {
                ProgressView()
                Text("Authenticating...")
            }
            .foregroundStyle(.secondary)
        case .connected(let session):
            Label("Connected as \(session.user.username)", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .error:
            EmptyView() // Error shown separately
        case .disconnected:
            EmptyView()
        }
    }
}
```

---

### Task 10: Library feature (grid + filters)

**Files:**
- Create: `mobile/ComfyGalleryMobile/Features/Library/LibraryFeature.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Library/LibraryView.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Library/MediaCell.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Library/FilterSheet.swift`

**Step 1: Write LibraryFeature.swift**

```swift
import SwiftUI
import OSLog

@MainActor
@Observable
final class LibraryFeature {
    var items: [MobileMediaSummary] = []
    var total: Int = 0
    var isLoading = false
    var isLoadingMore = false
    var errorMessage: String?
    var currentOffset: Int = 0
    var filterKind: MediaKind?
    var filterEvaluationState: EvaluationState?
    var filterTrash: FilterTrashOption = .hide
    private let limit = 48

    private let apiClient: APIClient
    private let mediaRepository: MediaRepository

    enum FilterTrashOption: CaseIterable {
        case hide, only, include

        var label: String {
            switch self {
            case .hide: return "Hide Trash"
            case .only: return "Trash Only"
            case .include: return "Include Trash"
            }
        }

        var queryValue: Bool? {
            switch self {
            case .hide: return false
            case .only: return true
            case .include: return nil
            }
        }
    }

    init(apiClient: APIClient, mediaRepository: MediaRepository) {
        self.apiClient = apiClient
        self.mediaRepository = mediaRepository
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        currentOffset = 0
        do {
            let page: MediaPage = try await apiClient.request(
                .mediaList(
                    kind: filterKind,
                    evaluationState: filterEvaluationState,
                    trash: filterTrash.queryValue,
                    sort: "file_created_desc",
                    limit: limit,
                    offset: 0
                )
            )
            items = page.items
            total = page.total
            currentOffset = page.items.count
        } catch {
            errorMessage = "Could not load media."
        }
        isLoading = false
    }

    func loadMoreIfNeeded(currentItem: MobileMediaSummary) {
        guard let lastItem = items.last,
              currentItem.id == lastItem.id,
              items.count < total,
              !isLoadingMore else { return }
        Task { await loadMore() }
    }

    private func loadMore() async {
        isLoadingMore = true
        do {
            let page: MediaPage = try await apiClient.request(
                .mediaList(
                    kind: filterKind,
                    evaluationState: filterEvaluationState,
                    trash: filterTrash.queryValue,
                    sort: "file_created_desc",
                    limit: limit,
                    offset: currentOffset
                )
            )
            items.append(contentsOf: page.items)
            currentOffset += page.items.count
        } catch {
            // Silently fail on pagination
        }
        isLoadingMore = false
    }

    func applyFilters() {
        Task { await load() }
    }
}
```

**Step 2: Write MediaCell.swift**

```swift
import SwiftUI

struct MediaCell: View {
    let item: MobileMediaSummary
    @Environment(MediaRepository.self) private var mediaRepository

    @State private var image: UIImage?
    @State private var loadFailed = false

    private let targetSize = CGSize(width: 200, height: 300)

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                if let image = image {
                    Image(uiImage: image)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: geometry.size.width, height: geometry.size.height)
                        .clipped()
                } else if loadFailed {
                    Color(.systemGray6)
                        .overlay {
                            Image(systemName: item.kind == .video ? "play.slash" : "photo")
                                .foregroundStyle(.secondary)
                        }
                } else {
                    Color(.systemGray6)
                        .overlay {
                            ProgressView()
                        }
                }

                // Overlays
                VStack {
                    HStack {
                        Spacer()
                        if item.kind == .video {
                            Image(systemName: "play.rectangle.fill")
                                .font(.caption)
                                .foregroundStyle(.white)
                                .padding(6)
                                .background(.black.opacity(0.5))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                                .padding(4)
                        }
                    }
                    Spacer()
                    HStack {
                        if item.isTrash == true {
                            Image(systemName: "trash.fill")
                                .font(.caption)
                                .foregroundStyle(.red)
                                .padding(4)
                        }
                        Spacer()
                        if let state = item.evaluationState {
                            evaluationIndicator(state)
                                .padding(4)
                        }
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .aspectRatio(2.0/3.0, contentMode: .fit)
        .task {
            guard image == nil, !loadFailed, let previewURL = URL(string: item.previewURL) else { return }
            do {
                image = try await mediaRepository.fetchPreviewImage(
                    mediaID: item.id,
                    previewURL: previewURL.absoluteString,
                    targetSize: targetSize
                )
            } catch {
                loadFailed = true
            }
        }
    }

    @ViewBuilder
    private func evaluationIndicator(_ state: EvaluationState) -> some View {
        switch state {
        case .complete:
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .inProgress:
            Image(systemName: "circle.dotted")
                .foregroundStyle(.orange)
        case .notStarted:
            Image(systemName: "circle")
                .foregroundStyle(.secondary)
        }
    }
}
```

**Step 3: Write FilterSheet.swift**

```swift
import SwiftUI

struct FilterSheet: View {
    @Binding var kind: MediaKind?
    @Binding var evaluationState: EvaluationState?
    @Binding var trash: LibraryFeature.FilterTrashOption
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Media Type") {
                    Button("All") { kind = nil }
                        .foregroundStyle(kind == nil ? .tint : .primary)
                    Button("Images") { kind = .image }
                        .foregroundStyle(kind == .image ? .tint : .primary)
                    Button("Videos") { kind = .video }
                        .foregroundStyle(kind == .video ? .tint : .primary)
                }

                Section("Evaluation Status") {
                    Button("All") { evaluationState = nil }
                        .foregroundStyle(evaluationState == nil ? .tint : .primary)
                    Button("Not Started") { evaluationState = .notStarted }
                        .foregroundStyle(evaluationState == .notStarted ? .tint : .primary)
                    Button("In Progress") { evaluationState = .inProgress }
                        .foregroundStyle(evaluationState == .inProgress ? .tint : .primary)
                    Button("Complete") { evaluationState = .complete }
                        .foregroundStyle(evaluationState == .complete ? .tint : .primary)
                }

                Section("Trash") {
                    ForEach(LibraryFeature.FilterTrashOption.allCases, id: \.self) { option in
                        Button(option.label) { trash = option }
                            .foregroundStyle(trash == option ? .tint : .primary)
                    }
                }
            }
            .navigationTitle("Filters")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
```

**Step 4: Write LibraryView.swift**

```swift
import SwiftUI

struct LibraryView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: LibraryFeature
    @State private var showingFilters = false
    @State private var selectedItem: MobileMediaSummary?
    @State private var showingViewer = false

    init() {
        _feature = State(initialValue: LibraryFeature(
            apiClient: AppEnvironment().apiClient,
            mediaRepository: AppEnvironment().mediaRepository
        ))
    }

    var body: some View {
        NavigationStack {
            Group {
                if feature.isLoading && feature.items.isEmpty {
                    ProgressView("Loading...")
                } else if let error = feature.errorMessage, feature.items.isEmpty {
                    VStack(spacing: 12) {
                        Text(error)
                            .foregroundStyle(.secondary)
                        Button("Retry") {
                            Task { await feature.load() }
                        }
                        .buttonStyle(.bordered)
                    }
                } else if feature.items.isEmpty {
                    Text("No media matched this view.")
                        .foregroundStyle(.secondary)
                } else {
                    gridView
                }
            }
            .navigationTitle("Library")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingFilters = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                            .symbolVariant(filtersActive ? .fill : .none)
                    }
                }
            }
            .sheet(isPresented: $showingFilters) {
                FilterSheet(
                    kind: $feature.filterKind,
                    evaluationState: $feature.filterEvaluationState,
                    trash: $feature.filterTrash
                )
                .onDisappear {
                    feature.applyFilters()
                }
            }
            .fullScreenCover(isPresented: $showingViewer) {
                if let item = selectedItem {
                    ViewerFeatureView(initialItem: item, items: feature.items)
                }
            }
        }
        .task {
            if feature.items.isEmpty {
                await feature.load()
            }
        }
    }

    private var filtersActive: Bool {
        feature.filterKind != nil || feature.filterEvaluationState != nil || feature.filterTrash != .hide
    }

    private var gridView: some View {
        ScrollView {
            LazyVGrid(
                columns: [
                    GridItem(.adaptive(minimum: 120), spacing: 8)
                ],
                spacing: 8
            ) {
                ForEach(feature.items) { item in
                    MediaCell(item: item)
                        .onTapGesture {
                            selectedItem = item
                            showingViewer = true
                        }
                        .onAppear {
                            feature.loadMoreIfNeeded(currentItem: item)
                        }
                }
            }
            .padding(12)
        }
    }
}
```

---

### Task 11: Viewer feature

**Files:**
- Create: `mobile/ComfyGalleryMobile/Features/Viewer/ViewerFeatureView.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Viewer/ImageViewer.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Viewer/VideoPlayerView.swift`

**Step 1: Write ImageViewer.swift**

```swift
import SwiftUI

struct ImageViewer: View {
    let image: UIImage
    @State private var scale: CGFloat = 1.0
    @State private var lastScale: CGFloat = 1.0
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero

    var body: some View {
        GeometryReader { geometry in
            Image(uiImage: image)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .scaleEffect(scale)
                .offset(offset)
                .gesture(
                    MagnificationGesture()
                        .onChanged { value in
                            let delta = value / lastScale
                            lastScale = value
                            scale = min(max(scale * delta, 1), 5)
                        }
                        .onEnded { _ in
                            lastScale = 1.0
                        }
                )
                .gesture(
                    DragGesture()
                        .onChanged { value in
                            offset = CGSize(
                                width: lastOffset.width + value.translation.width,
                                height: lastOffset.height + value.translation.height
                            )
                        }
                        .onEnded { _ in
                            lastOffset = offset
                        }
                )
                .onTapGesture(count: 2) {
                    withAnimation {
                        if scale > 1.0 {
                            scale = 1.0
                            offset = .zero
                            lastOffset = .zero
                        } else {
                            scale = 2.0
                        }
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .clipped()
        }
    }
}
```

**Step 2: Write VideoPlayerView.swift**

```swift
import SwiftUI
import AVKit

struct VideoPlayerView: View {
    let videoURL: URL
    let posterImage: UIImage?

    @State private var player: AVPlayer?
    @State private var isMuted = false

    var body: some View {
        Group {
            if let player = player {
                VideoPlayer(player: player)
                    .onAppear {
                        player.isMuted = isMuted
                    }
            } else if let poster = posterImage {
                Image(uiImage: poster)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .overlay {
                        ProgressView()
                            .scaleEffect(1.5)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .background(.ultraThinMaterial)
                    }
            }
        }
        .onAppear {
            player = AVPlayer(url: videoURL)
            player?.isMuted = isMuted
        }
        .onDisappear {
            player?.pause()
            player = nil
        }
        .toolbar {
            ToolbarItem(placement: .bottomBar) {
                Button {
                    isMuted.toggle()
                    player?.isMuted = isMuted
                } label: {
                    Image(systemName: isMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                }
            }
        }
    }
}
```

**Step 3: Write ViewerFeatureView.swift**

```swift
import SwiftUI

struct ViewerFeatureView: View {
    let initialItem: MobileMediaSummary
    let items: [MobileMediaSummary]

    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    @State private var currentIndex: Int
    @State private var image: UIImage?
    @State private var videoURL: URL?
    @State private var posterImage: UIImage?
    @State private var isLoading = true
    @State private var showControls = true

    init(initialItem: MobileMediaSummary, items: [MobileMediaSummary]) {
        self.initialItem = initialItem
        self.items = items
        _currentIndex = State(initialValue: items.firstIndex(where: { $0.id == initialItem.id }) ?? 0)
    }

    var currentItem: MobileMediaSummary? {
        guard currentIndex >= 0, currentIndex < items.count else { return nil }
        return items[currentIndex]
    }

    var body: some View {
        NavigationStack {
            GeometryReader { geometry in
                ZStack {
                    Color.black.ignoresSafeArea()

                    if let item = currentItem {
                        if isLoading {
                            ProgressView()
                                .tint(.white)
                        } else if item.kind == .video, let url = videoURL {
                            VideoPlayerView(videoURL: url, posterImage: posterImage)
                        } else if let image = image {
                            ImageViewer(image: image)
                        }
                    }
                }
                .overlay(alignment: .top) {
                    if showControls {
                        HStack {
                            Button {
                                dismiss()
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(.white)
                                    .shadow(radius: 2)
                            }

                            Spacer()

                            Text("\(currentIndex + 1) / \(items.count)")
                                .foregroundStyle(.white)
                                .font(.subheadline)
                        }
                        .padding()
                        .background(.black.opacity(0.4))
                    }
                }
                .overlay(alignment: .bottom) {
                    if showControls {
                        HStack {
                            Button {
                                navigateToPrevious()
                            } label: {
                                Image(systemName: "arrow.left.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(currentIndex > 0 ? .white : .gray)
                            }
                            .disabled(currentIndex <= 0)

                            Spacer()

                            Button {
                                navigateToNext()
                            } label: {
                                Image(systemName: "arrow.right.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(currentIndex < items.count - 1 ? .white : .gray)
                            }
                            .disabled(currentIndex >= items.count - 1)
                        }
                        .padding()
                        .background(.black.opacity(0.4))
                    }
                }
                .onTapGesture {
                    withAnimation {
                        showControls.toggle()
                    }
                }
            }
            .navigationBarHidden(true)
        }
        .task {
            await loadCurrentItem()
        }
        .onChange(of: currentIndex) { _, _ in
            Task { await loadCurrentItem() }
        }
    }

    private func loadCurrentItem() async {
        guard let item = currentItem else { return }
        isLoading = true
        image = nil
        videoURL = nil
        posterImage = nil

        do {
            let repo = environment.mediaRepository
            if item.kind == .video, let playbackURL = URL(string: item.previewURL) {
                videoURL = try await repo.fetchPlaybackVideo(mediaID: item.id)
            }
            if let previewURL = URL(string: item.previewURL) {
                let targetSize = CGSize(width: UIScreen.main.bounds.width, height: UIScreen.main.bounds.width * 1.5)
                posterImage = try await repo.fetchPreviewImage(
                    mediaID: item.id,
                    previewURL: previewURL.absoluteString,
                    targetSize: targetSize
                )
                if item.kind == .image {
                    image = posterImage
                }
            }
        } catch {
            // Keep loading indicator or show error
        }
        isLoading = false
    }

    private func navigateToPrevious() {
        guard currentIndex > 0 else { return }
        currentIndex -= 1
    }

    private func navigateToNext() {
        guard currentIndex < items.count - 1 else { return }
        currentIndex += 1
    }
}
```

---

### Task 12: Review home feature

**Files:**
- Create: `mobile/ComfyGalleryMobile/Features/ReviewHome/ReviewHomeFeature.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewHome/ReviewHomeView.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewHome/NewSessionSheet.swift`

**Step 1: Write ReviewHomeFeature.swift**

```swift
import SwiftUI
import OSLog

@MainActor
@Observable
final class ReviewHomeFeature {
    var summary: ReviewSummary?
    var sessions: [ReviewSession] = []
    var isLoading = false
    var errorMessage: String?

    // New session form
    var sourceKind: SourceKind = .random
    var filterKind: MediaKind?
    var filterEvaluationState: EvaluationState?
    var randomLimit: Int = 100
    var orderingMode: OrderingMode = .random
    var includeCharacter: Bool = false

    private let apiClient: APIClient

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            async let summary: ReviewSummary = apiClient.request(.reviewSummary)
            async let sessions: [ReviewSession] = apiClient.request(.reviewSessions(limit: 25))
            self.summary = try await summary
            self.sessions = try await sessions
        } catch {
            errorMessage = "Could not load review data."
        }
        isLoading = false
    }

    func createSession() async -> ReviewSession? {
        let request = CreateSessionRequest(
            name: nil,
            sourceKind: sourceKind,
            filter: sourceKind == .filter
                ? MediaFilter(kind: filterKind, evaluationState: filterEvaluationState, trash: false)
                : nil,
            randomLimit: randomLimit,
            orderingMode: orderingMode,
            optionalModules: includeCharacter ? ["character"] : []
        )
        do {
            let session: ReviewSession = try await apiClient.request(.createReviewSession(request))
            await load()
            return session
        } catch {
            errorMessage = "Could not create review session."
            return nil
        }
    }

    func deleteSession(_ session: ReviewSession) async {
        do {
            let _: EmptyResponse = try await apiClient.request(.deleteReviewSession(id: session.id))
            await load()
        } catch {
            errorMessage = "Could not delete session."
        }
    }
}

struct EmptyResponse: Decodable {}
```

**Step 2: Write NewSessionSheet.swift**

```swift
import SwiftUI

struct NewSessionSheet: View {
    @Bindable var feature: ReviewHomeFeature
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Picker("Source", selection: $feature.sourceKind) {
                        Text("Random Unevaluated").tag(SourceKind.random)
                        Text("In Progress").tag(SourceKind.inProgress)
                        Text("Current Library View").tag(SourceKind.filter)
                    }

                    if feature.sourceKind == .filter {
                        Picker("Media Type", selection: Binding(
                            get: { feature.filterKind },
                            set: { feature.filterKind = $0 }
                        )) {
                            Text("All").tag(nil as MediaKind?)
                            Text("Images").tag(MediaKind.image as MediaKind?)
                            Text("Videos").tag(MediaKind.video as MediaKind?)
                        }
                    }
                }

                Section("Settings") {
                    Stepper("Max Items: \(feature.randomLimit)", value: $feature.randomLimit, in: 1...2000, step: 10)

                    Picker("Ordering", selection: $feature.orderingMode) {
                        Text("Random").tag(OrderingMode.random)
                        Text("Stable").tag(OrderingMode.stable)
                    }

                    Toggle("Character Rubric", isOn: $feature.includeCharacter)
                }
            }
            .navigationTitle("New Review")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Start Review") {
                        Task {
                            let session = await feature.createSession()
                            if session != nil {
                                dismiss()
                            }
                        }
                    }
                }
            }
        }
    }
}
```

**Step 3: Write ReviewHomeView.swift**

```swift
import SwiftUI

struct ReviewHomeView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: ReviewHomeFeature
    @State private var showingNewSession = false
    @State private var selectedSession: ReviewSession?
    @State private var showingWorkspace = false

    init() {
        _feature = State(initialValue: ReviewHomeFeature(
            apiClient: AppEnvironment().apiClient
        ))
    }

    var body: some View {
        NavigationStack {
            List {
                // Continue section
                if let summary = feature.summary {
                    Section("Overview") {
                        HStack {
                            Label("Not Started", systemImage: "circle")
                            Spacer()
                            Text("\(summary.notStartedCount)")
                                .foregroundStyle(.secondary)
                        }
                        HStack {
                            Label("In Progress", systemImage: "circle.dotted")
                            Spacer()
                            Text("\(summary.inProgressCount)")
                                .foregroundStyle(.secondary)
                        }
                        HStack {
                            Label("Complete", systemImage: "checkmark.circle.fill")
                            Spacer()
                            Text("\(summary.completeCount)")
                                .foregroundStyle(.secondary)
                        }
                    }

                    // Quick actions
                    Section("Quick Actions") {
                        Button {
                            feature.sourceKind = .inProgress
                            feature.randomLimit = summary.inProgressCount
                            showingNewSession = true
                        } label: {
                            Label("Resume In Progress (\(summary.inProgressCount))", systemImage: "arrow.counterclockwise")
                        }

                        Button {
                            feature.sourceKind = .random
                            feature.randomLimit = 100
                            showingNewSession = true
                        } label: {
                            Label("Start Random Review", systemImage: "shuffle")
                        }
                    }
                }

                // Active sessions
                let activeSessions = feature.sessions.filter { $0.status == .active }
                if !activeSessions.isEmpty {
                    Section("Active Sessions") {
                        ForEach(activeSessions) { session in
                            sessionRow(session)
                        }
                    }
                }

                // Recent sessions
                let otherSessions = feature.sessions.filter { $0.status != .active }
                if !otherSessions.isEmpty {
                    Section("Recent Sessions") {
                        ForEach(otherSessions) { session in
                            sessionRow(session)
                        }
                    }
                }
            }
            .navigationTitle("Review")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingNewSession = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingNewSession) {
                NewSessionSheet(feature: feature)
            }
            .fullScreenCover(item: $selectedSession) { session in
                ReviewWorkspaceView(
                    feature: ReviewWorkspaceFeature(
                        sessionID: session.id,
                        apiClient: environment.apiClient,
                        mediaRepository: environment.mediaRepository,
                        commandQueue: environment.reviewCommandQueue,
                        localStore: environment.localStore
                    )
                )
            }
            .refreshable {
                await feature.load()
            }
            .task {
                await feature.load()
            }
        }
    }

    @ViewBuilder
    private func sessionRow(_ session: ReviewSession) -> some View {
        Button {
            selectedSession = session
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(session.name ?? session.sourceKind.rawValue.capitalized)
                        .font(.headline)
                    Spacer()
                    sessionStatusBadge(session.status)
                }
                if let cursor = session.currentCursor {
                    Text("Position: \(cursor) / \(session.candidateCount)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                if let counts = session.progressCounts {
                    Text("\(counts.complete) complete · \(counts.inProgress) in progress")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                if let lastOpened = session.lastOpenedAt {
                    Text("Last opened: \(lastOpened)")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .swipeActions {
            Button("Delete", role: .destructive) {
                Task { await feature.deleteSession(session) }
            }
        }
    }

    @ViewBuilder
    private func sessionStatusBadge(_ status: SessionStatus) -> some View {
        switch status {
        case .active:
            Text("Active")
                .font(.caption)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(.green.opacity(0.15))
                .foregroundStyle(.green)
                .clipShape(Capsule())
        case .finished:
            Text("Finished")
                .font(.caption)
                .foregroundStyle(.secondary)
        case .abandoned:
            Text("Abandoned")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
    }
}
```

---

### Task 13: Review workspace feature (blind review)

**Files:**
- Create: `mobile/ComfyGalleryMobile/Features/ReviewWorkspace/ReviewWorkspaceFeature.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewWorkspace/ReviewWorkspaceView.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewWorkspace/CriterionCard.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewWorkspace/PromptSection.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewWorkspace/SaveStateIndicator.swift`
- Create: `mobile/ComfyGalleryMobile/Features/ReviewWorkspace/ConflictSheet.swift`

**Step 1: Write ReviewWorkspaceFeature.swift** (the most complex feature model)

```swift
import SwiftUI
import OSLog

@MainActor
@Observable
final class ReviewWorkspaceFeature {
    let sessionID: String
    var reviewItem: ReviewItem?
    var position: Int = 0
    var isLoading = true
    var errorMessage: String?
    var saveState: SaveState = .saved

    // Conflict state
    var showConflict = false
    var conflictMessage = ""
    var conflictServerValue: String = ""
    var conflictLocalValue: String = ""
    private var conflictResolution: ((Bool) -> Void)?

    private let apiClient: APIClient
    private let mediaRepository: MediaRepository
    private let commandQueue: ReviewCommandQueue
    private let localStore: LocalStore
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "ReviewWorkspace")

    enum SaveState {
        case saved, saving, savedLocally, needsAttention
    }

    init(
        sessionID: String,
        apiClient: APIClient,
        mediaRepository: MediaRepository,
        commandQueue: ReviewCommandQueue,
        localStore: LocalStore
    ) {
        self.sessionID = sessionID
        self.apiClient = apiClient
        self.mediaRepository = mediaRepository
        self.commandQueue = commandQueue
        self.localStore = localStore
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            try await fetchCurrentItem()
        } catch {
            errorMessage = "Could not load review item."
        }
        isLoading = false
    }

    private func fetchCurrentItem() async throws {
        let item: ReviewItem = try await apiClient.request(
            .reviewItem(sessionID: sessionID, position: position)
        )
        reviewItem = item
        position = item.position
    }

    // MARK: - Navigation

    func navigateToPrevious() async {
        guard position > 0, saveState != .saving else { return }
        do {
            try await updateCursor(position - 1)
            position -= 1
            await load()
        } catch {
            errorMessage = "Could not navigate."
        }
    }

    func navigateToNext() async {
        guard let item = reviewItem, position < item.session.candidateCount - 1,
              saveState != .saving else { return }
        do {
            try await updateCursor(position + 1)
            position += 1
            await load()
        } catch {
            errorMessage = "Could not navigate."
        }
    }

    func stop() async {
        // Persist current state and return; does not change session status
        // Pending commands are stored locally
    }

    private func updateCursor(_ cursor: Int) async throws {
        let body = PatchSessionBody(currentCursor: cursor, status: nil)
        let _: ReviewSession = try await apiClient.request(.patchReviewSession(id: sessionID, body))
    }

    // MARK: - Scoring

    func setScore(_ value: Int, for criterion: Criterion, evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "",
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion.id,
            commandKind: .score,
            intendedValue: value,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch let error as APIError {
            if case .conflict = error {
                saveState = .needsAttention
                await handleConflict(
                    message: error.localizedDescription,
                    serverValue: "",
                    localValue: "\(value)"
                )
            } else {
                saveState = .savedLocally
            }
        } catch {
            saveState = .savedLocally
        }
    }

    func setNA(for criterion: Criterion, evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "",
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion.id,
            commandKind: .na,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch {
            saveState = .savedLocally
        }
    }

    func clearScore(for criterion: Criterion, evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "",
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            criterionVersionUUID: criterion.id,
            commandKind: .clear,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch {
            saveState = .savedLocally
        }
    }

    func toggleTrash(evaluation: Evaluation) async {
        saveState = .saving
        let mutation = PendingMutation(
            serverProfileUUID: "",
            reviewSessionUUID: sessionID,
            mediaUUID: reviewItem?.media.id ?? "",
            evaluationUUID: evaluation.id,
            commandKind: evaluation.isTrash ? .restore : .trash,
            baseEvaluationVersion: evaluation.version
        )
        do {
            try localStore.insertPendingMutation(mutation)
            await commandQueue.enqueue(mutation)
            try await fetchCurrentItem()
            saveState = .saved
        } catch {
            saveState = .savedLocally
        }
    }

    // MARK: - Undo

    func undoLastAction() async {
        // Fetch current item and compare with local state
        // For V1: re-fetch and allow re-scoring
        try? await fetchCurrentItem()
        saveState = .saved
    }

    // MARK: - Conflict

    private func handleConflict(message: String, serverValue: String, localValue: String) async {
        conflictMessage = message
        conflictServerValue = serverValue
        conflictLocalValue = localValue
        showConflict = true
    }

    func resolveConflict(useServerValue: Bool) async {
        showConflict = false
        if useServerValue {
            try? await fetchCurrentItem()
            saveState = .saved
        } else {
            // Reapply: will be handled by the caller
        }
    }

    func finishSession() async {
        let body = PatchSessionBody(currentCursor: nil, status: .finished)
        do {
            let _: ReviewSession = try await apiClient.request(.patchReviewSession(id: sessionID, body))
        } catch {
            errorMessage = "Could not finish session."
        }
    }

    // MARK: - Computed

    var currentEvaluation: Evaluation? {
        reviewItem?.evaluations.first
    }

    var scoreForCriterion: (Criterion) -> EvaluationScore? {
        { criterion in
            self.currentEvaluation?.scores.first { $0.criterionVersionId == criterion.id }
        }
    }

    var isLastItem: Bool {
        guard let item = reviewItem else { return false }
        return item.position >= item.session.candidateCount - 1
    }
}
```

**Step 2: Write CriterionCard.swift**

```swift
import SwiftUI

struct CriterionCard: View {
    let criterion: Criterion
    let score: EvaluationScore?
    let evaluation: Evaluation
    let onScore: (Int) -> Void
    let onClear: () -> Void
    let onNA: () -> Void
    let isDisabled: Bool

    @State private var sliderValue: Double = -1

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(criterion.label)
                    .font(.headline)
                Spacer()
                scoreStateChip
            }

            if let description = criterion.description {
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 8) {
                Slider(value: Binding(
                    get: { sliderValue },
                    set: { newValue in
                        let intValue = Int(newValue.rounded())
                        if intValue != Int(sliderValue.rounded()) {
                            let generator = UISelectionFeedbackGenerator()
                            generator.selectionChanged()
                        }
                        sliderValue = Double(intValue)
                    }
                ), in: -1...10, step: 1)
                .disabled(isDisabled)

                HStack {
                    Text("0")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("5")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("10")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .onAppear {
                if let score = score, score.state == .scored, let value = score.value {
                    sliderValue = Double(value)
                } else {
                    sliderValue = -1
                }
            }
            .onChange(of: sliderValue) { _, newValue in
                let intValue = Int(newValue.rounded())
                if intValue >= 0 {
                    onScore(intValue)
                }
            }

            HStack(spacing: 12) {
                Button {
                    sliderValue = -1
                    onClear()
                } label: {
                    Label("Clear", systemImage: "xmark")
                        .font(.caption)
                }
                .buttonStyle(.bordered)
                .disabled(isDisabled)

                Spacer()

                Button {
                    onNA()
                } label: {
                    Label("N/A", systemImage: "nosign")
                        .font(.caption)
                }
                .buttonStyle(.bordered)
                .disabled(isDisabled)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var scoreStateChip: some View {
        if let score = score {
            switch score.state {
            case .scored:
                Text("\(score.value ?? -1) / 10")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(.tint.opacity(0.15))
                    .foregroundStyle(.tint)
                    .clipShape(Capsule())
            case .na:
                Text("N/A")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(.orange.opacity(0.15))
                    .foregroundStyle(.orange)
                    .clipShape(Capsule())
            case .unset:
                Text("—")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        } else {
            Text("—")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
```

**Step 3: Write PromptSection.swift**

```swift
import SwiftUI

struct PromptSection: View {
    let prompts: [ReviewPrompt]

    @State private var expandedPromptIndex: Int? = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if prompts.isEmpty {
                Text("No prompt was extracted for this media.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(prompts.enumerated()), id: \.offset) { index, prompt in
                    VStack(alignment: .leading, spacing: 4) {
                        Button {
                            withAnimation {
                                expandedPromptIndex = expandedPromptIndex == index ? nil : index
                            }
                        } label: {
                            HStack {
                                Text(prompt.label)
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                Spacer()
                                Image(systemName: expandedPromptIndex == index
                                    ? "chevron.up"
                                    : "chevron.down")
                                    .font(.caption)
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)

                        if expandedPromptIndex == index {
                            Text(prompt.text)
                                .font(.body)
                                .textSelection(.enabled)
                                .padding(.top, 4)

                            if prompt.text.count > 300 {
                                Button("Show Less") {
                                    withAnimation { expandedPromptIndex = nil }
                                }
                                .font(.caption)
                            }
                        } else if prompt.text.count > 300 {
                            Text(String(prompt.text.prefix(300)) + "...")
                                .font(.body)
                                .lineLimit(4)
                                .padding(.top, 4)

                            Button("Show More") {
                                withAnimation { expandedPromptIndex = index }
                            }
                            .font(.caption)
                        }
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }
}
```

**Step 4: Write SaveStateIndicator.swift**

```swift
import SwiftUI

struct SaveStateIndicator: View {
    let state: ReviewWorkspaceFeature.SaveState

    var body: some View {
        HStack(spacing: 4) {
            switch state {
            case .saved:
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                Text("Saved")
                    .foregroundStyle(.secondary)
            case .saving:
                ProgressView()
                    .scaleEffect(0.7)
                Text("Saving...")
                    .foregroundStyle(.secondary)
            case .savedLocally:
                Image(systemName: "arrow.down.circle.fill")
                    .foregroundStyle(.orange)
                Text("Saved locally")
                    .foregroundStyle(.secondary)
            case .needsAttention:
                Image(systemName: "exclamationmark.circle.fill")
                    .foregroundStyle(.red)
                Text("Needs attention")
                    .foregroundStyle(.red)
            }
        }
        .font(.caption)
    }
}
```

**Step 5: Write ConflictSheet.swift**

```swift
import SwiftUI

struct ConflictSheet: View {
    let message: String
    let serverValue: String
    let localValue: String
    let onResolve: (Bool) -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 40))
                    .foregroundStyle(.orange)

                Text("This score changed elsewhere")
                    .font(.headline)

                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                VStack(spacing: 8) {
                    HStack {
                        Text("Server value:")
                        Spacer()
                        Text(serverValue)
                            .fontWeight(.medium)
                    }
                    HStack {
                        Text("Your value:")
                        Spacer()
                        Text(localValue)
                            .fontWeight(.medium)
                    }
                }
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))

                VStack(spacing: 12) {
                    Button {
                        onResolve(true)
                    } label: {
                        Text("Use Server Value")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    Button {
                        onResolve(false)
                    } label: {
                        Text("Reapply My Value")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
            .navigationTitle("Conflict")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
```

**Step 6: Write ReviewWorkspaceView.swift**

```swift
import SwiftUI

struct ReviewWorkspaceView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @State var feature: ReviewWorkspaceFeature

    var body: some View {
        VStack(spacing: 0) {
            // Fixed header
            HStack {
                Button("Stop") {
                    Task { await feature.stop() }
                    dismiss()
                }

                Spacer()

                if let item = feature.reviewItem {
                    Text("\(item.position + 1) / \(item.session.candidateCount)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                SaveStateIndicator(state: feature.saveState)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(.bar)

            if feature.isLoading {
                Spacer()
                ProgressView("Loading...")
                Spacer()
            } else if let error = feature.errorMessage {
                Spacer()
                VStack(spacing: 12) {
                    Text(error)
                        .foregroundStyle(.secondary)
                    Button("Retry") {
                        Task { await feature.load() }
                    }
                }
                Spacer()
            } else if let item = feature.reviewItem {
                // Media stage (fixed)
                mediaStage(media: item.media)
                    .frame(maxHeight: UIScreen.main.bounds.height * 0.48)

                Divider()

                // Scrollable criteria
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        // Prompts
                        PromptSection(prompts: item.prompts)

                        // Evaluations and criteria
                        ForEach(item.evaluations) { evaluation in
                            VStack(alignment: .leading, spacing: 12) {
                                Text(evaluation.evaluationKind == "character"
                                    ? "Character"
                                    : "Core Evaluation")
                                    .font(.title3)
                                    .fontWeight(.semibold)

                                ForEach(evaluation.criteria) { criterion in
                                    CriterionCard(
                                        criterion: criterion,
                                        score: evaluation.scores.first { $0.criterionVersionId == criterion.id },
                                        evaluation: evaluation,
                                        onScore: { value in
                                            Task { await feature.setScore(value, for: criterion, evaluation: evaluation) }
                                        },
                                        onClear: {
                                            Task { await feature.clearScore(for: criterion, evaluation: evaluation) }
                                        },
                                        onNA: {
                                            Task { await feature.setNA(for: criterion, evaluation: evaluation) }
                                        },
                                        isDisabled: feature.saveState == .saving
                                    )
                                }

                                // Trash / Restore
                                Button {
                                    Task { await feature.toggleTrash(evaluation: evaluation) }
                                } label: {
                                    Label(
                                        evaluation.isTrash ? "Restore from Trash" : "Mark as Trash",
                                        systemImage: evaluation.isTrash ? "arrow.uturn.backward" : "trash"
                                    )
                                    .frame(maxWidth: .infinity)
                                }
                                .buttonStyle(.bordered)
                                .tint(evaluation.isTrash ? .green : .red)
                                .padding(.top, 8)
                            }
                        }
                    }
                    .padding()
                }
            }

            // Fixed bottom navigation
            Divider()
            HStack {
                Button {
                    Task { await feature.navigateToPrevious() }
                } label: {
                    Label("Previous", systemImage: "arrow.left")
                }
                .disabled(feature.position <= 0)

                Spacer()

                Button {
                    Task { await feature.undoLastAction() }
                } label: {
                    Label("Undo", systemImage: "arrow.uturn.backward")
                }

                Spacer()

                if feature.isLastItem {
                    Button("Finish Session") {
                        Task { await feature.finishSession() }
                        dismiss()
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    Button {
                        Task { await feature.navigateToNext() }
                    } label: {
                        Label("Next", systemImage: "arrow.right")
                    }
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(.bar)
        }
        .sheet(isPresented: $feature.showConflict) {
            ConflictSheet(
                message: feature.conflictMessage,
                serverValue: feature.conflictServerValue,
                localValue: feature.conflictLocalValue,
                onResolve: { useServer in
                    Task { await feature.resolveConflict(useServerValue: useServer) }
                }
            )
        }
        .task {
            await feature.load()
        }
    }

    @ViewBuilder
    private func mediaStage(media: ReviewMedia) -> some View {
        Group {
            if media.kind == .video {
                // Video handled via MediaRepository fetch
                Rectangle()
                    .fill(Color(.systemGray6))
                    .overlay {
                        Image(systemName: "play.rectangle")
                            .font(.system(size: 48))
                            .foregroundStyle(.secondary)
                    }
            } else {
                Rectangle()
                    .fill(Color(.systemGray6))
                    .overlay {
                        Image(systemName: "photo")
                            .font(.system(size: 48))
                            .foregroundStyle(.secondary)
                    }
            }
        }
        .accessibilityLabel(media.kind == .video ? "Video under review" : "Image under review")
    }
}
```

---

### Task 14: Settings feature

**Files:**
- Create: `mobile/ComfyGalleryMobile/Features/Settings/SettingsView.swift`
- Create: `mobile/ComfyGalleryMobile/Features/Settings/SettingsFeature.swift`

**Step 1: Write SettingsFeature.swift**

```swift
import SwiftUI
import OSLog

@MainActor
@Observable
final class SettingsFeature {
    var showDisconnectConfirmation = false
    var privacyCoverEnabled = false
    var cacheSizeDescription: String = "Calculating..."
    var isClearingCache = false

    private let connectionService: ConnectionService
    private let mediaRepository: MediaRepository

    init(connectionService: ConnectionService, mediaRepository: MediaRepository) {
        self.connectionService = connectionService
        self.mediaRepository = mediaRepository
    }

    func disconnect() async {
        await connectionService.disconnect()
    }

    func clearCache() async {
        isClearingCache = true
        await mediaRepository.clearAllCaches()
        cacheSizeDescription = "0 bytes"
        isClearingCache = false
    }

    func updateCacheSize() async {
        // Calculate from MediaRepository
        cacheSizeDescription = "See MediaRepository"
    }
}
```

**Step 2: Write SettingsView.swift**

```swift
import SwiftUI

struct SettingsView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: SettingsFeature

    init() {
        _feature = State(initialValue: SettingsFeature(
            connectionService: AppEnvironment().connectionService,
            mediaRepository: AppEnvironment().mediaRepository
        ))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Connection") {
                    if case .connected(let session) = environment.connectionService.connectionState {
                        HStack {
                            Label("Connected as", systemImage: "person.fill")
                            Spacer()
                            Text(session.user.username)
                                .foregroundStyle(.secondary)
                        }
                    }

                    if let url = environment.connectionService.baseURL {
                        HStack {
                            Label("Server", systemImage: "network")
                            Spacer()
                            Text(url.absoluteString)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                    }

                    if let version = environment.connectionService.serverVersion {
                        HStack {
                            Label("Version", systemImage: "info.circle")
                            Spacer()
                            Text(version)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Button("Disconnect", role: .destructive) {
                        feature.showDisconnectConfirmation = true
                    }
                }

                Section("Privacy") {
                    Toggle("Privacy Cover in App Switcher", isOn: $feature.privacyCoverEnabled)
                        .onChange(of: feature.privacyCoverEnabled) { _, newValue in
                            // Implement privacy cover
                        }
                }

                Section("Cache") {
                    HStack {
                        Text("Cache Size")
                        Spacer()
                        Text(feature.cacheSizeDescription)
                            .foregroundStyle(.secondary)
                    }

                    Button("Clear Cache") {
                        Task { await feature.clearCache() }
                    }
                    .disabled(feature.isClearingCache)
                }

                Section("About") {
                    HStack {
                        Text("App Version")
                        Spacer()
                        Text("0.1.0")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .alert("Disconnect", isPresented: $feature.showDisconnectConfirmation) {
                Button("Disconnect", role: .destructive) {
                    Task { await feature.disconnect() }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will erase your saved token, pending changes, and cached media.")
            }
        }
    }
}
```

---

### Task 15: Design system and support utilities

**Files:**
- Create: `mobile/ComfyGalleryMobile/DesignSystem/DesignTokens.swift`
- Create: `mobile/ComfyGalleryMobile/Core/Support/Logger.swift`

**Step 1: Write DesignTokens.swift**

```swift
import SwiftUI

enum DesignTokens {
    static let cornerRadius: CGFloat = 12
    static let smallCornerRadius: CGFloat = 8
    static let spacing: CGFloat = 8
    static let largeSpacing: CGFloat = 16
    static let compactGridSpacing: CGFloat = 8
    static let regularGridSpacing: CGFloat = 12
    static let minimumTouchTarget: CGFloat = 44
}
```

**Step 2: Write Logger.swift**

```swift
import OSLog

extension Logger {
    static let subsystem = "com.comfygallery.mobile"

    static let api = Logger(subsystem: subsystem, category: "API")
    static let auth = Logger(subsystem: subsystem, category: "Auth")
    static let media = Logger(subsystem: subsystem, category: "Media")
    static let review = Logger(subsystem: subsystem, category: "Review")
    static let persistence = Logger(subsystem: subsystem, category: "Persistence")
    static let lifecycle = Logger(subsystem: subsystem, category: "Lifecycle")
}
```

---

### Task 16: Tests — Unit tests

**Files:**
- Create: `mobile/ComfyGalleryMobileTests/APIErrorTests.swift`
- Create: `mobile/ComfyGalleryMobileTests/APIClientTests.swift`
- Create: `mobile/ComfyGalleryMobileTests/EnumDecodingTests.swift`
- Create: `mobile/ComfyGalleryMobileTests/ImageDecoderTests.swift`
- Create: `mobile/ComfyGalleryMobileTests/ReviewCommandQueueTests.swift`
- Create: `mobile/ComfyGalleryMobileTests/VideoCacheTests.swift`
- Create: `mobile/ComfyGalleryMobileTests/CredentialStoreTests.swift`

**Step 1: Write APIErrorTests.swift**

```swift
import XCTest
@testable import ComfyGalleryMobile

final class APIErrorTests: XCTestCase {
    func testMap401ReturnsUnauthorized() {
        let error = APIError.map(statusCode: 401, envelope: nil)
        XCTAssertEqual(error, .unauthorized)
    }

    func testMap409ReturnsConflictWithEnvelope() {
        let envelope = APIErrorEnvelope(error: .init(
            code: "EVALUATION_VERSION_CONFLICT",
            message: "Changed since loaded.",
            details: nil,
            requestId: "req-123"
        ))
        let error = APIError.map(statusCode: 409, envelope: envelope)
        if case .conflict(let e) = error {
            XCTAssertEqual(e.error.code, "EVALUATION_VERSION_CONFLICT")
            XCTAssertEqual(e.error.requestId, "req-123")
        } else {
            XCTFail("Expected .conflict, got \(error)")
        }
    }

    func testMap500ReturnsServerError() {
        let error = APIError.map(statusCode: 500, envelope: nil)
        if case .serverError(let code) = error {
            XCTAssertEqual(code, 500)
        } else {
            XCTFail("Expected .serverError")
        }
    }

    func testRetryableErrors() {
        XCTAssertTrue(APIError.serverError(500).isRetryable)
        XCTAssertTrue(APIError.networkError(NSError(domain: "", code: -1)).isRetryable)
        XCTAssertFalse(APIError.unauthorized.isRetryable)
        XCTAssertFalse(APIError.conflict(APIErrorEnvelope(error: .init(code: "", message: "", details: nil, requestId: nil))).isRetryable)
    }

    func testRequiresReauthentication() {
        XCTAssertTrue(APIError.unauthorized.requiresReauthentication)
        XCTAssertTrue(APIError.forbidden.requiresReauthentication)
        XCTAssertFalse(APIError.notFound.requiresReauthentication)
    }

    static var allTests = [
        ("testMap401ReturnsUnauthorized", testMap401ReturnsUnauthorized),
        ("testMap409ReturnsConflictWithEnvelope", testMap409ReturnsConflictWithEnvelope),
        ("testMap500ReturnsServerError", testMap500ReturnsServerError),
        ("testRetryableErrors", testRetryableErrors),
        ("testRequiresReauthentication", testRequiresReauthentication),
    ]
}
```

**Step 2: Write EnumDecodingTests.swift**

```swift
import XCTest
@testable import ComfyGalleryMobile

final class EnumDecodingTests: XCTestCase {
    func testDecodeMediaPage() throws {
        let json = """
        {
            "items": [
                {
                    "id": "019f-test",
                    "kind": "image",
                    "evaluation_state": "in_progress",
                    "is_trash": false,
                    "preview_url": "/api/v1/media/019f-test/preview",
                    "filename": "should_be_ignored.jpg",
                    "sha256": "should_also_be_ignored"
                }
            ],
            "total": 1,
            "limit": 48,
            "offset": 0,
            "extra_field": "should_be_ignored"
        }
        """.data(using: .utf8)!

        let page = try JSONDecoder().decode(MediaPage.self, from: json)
        XCTAssertEqual(page.items.count, 1)
        XCTAssertEqual(page.items[0].id, "019f-test")
        XCTAssertEqual(page.items[0].kind, .image)
        XCTAssertEqual(page.items[0].evaluationState, .inProgress)
    }

    func testDecodeReviewItem() throws {
        let json = """
        {
            "session": {
                "id": "019f-session",
                "current_cursor": 5,
                "candidate_count": 100
            },
            "position": 5,
            "media": {
                "id": "019f-media",
                "kind": "image",
                "preview_url": "/api/v1/media/019f-media/preview",
                "playback_url": null,
                "width": 1024,
                "height": 1536,
                "duration_seconds": null
            },
            "prompts": [
                {"role": "positive", "label": "Prompt", "text": "A beautiful landscape"}
            ],
            "evaluations": [
                {
                    "id": "019f-eval",
                    "evaluation_kind": "base",
                    "progress_state": "in_progress",
                    "is_trash": false,
                    "version": 3,
                    "criteria": [
                        {"id": "019f-crit", "label": "Aesthetic appeal", "description": null, "min_value": 0, "max_value": 10}
                    ],
                    "scores": []
                }
            ]
        }
        """.data(using: .utf8)!

        let item = try JSONDecoder().decode(ReviewItem.self, from: json)
        XCTAssertEqual(item.position, 5)
        XCTAssertEqual(item.media.kind, .image)
        XCTAssertEqual(item.prompts.count, 1)
        XCTAssertEqual(item.evaluations.count, 1)
        XCTAssertEqual(item.evaluations[0].criteria.count, 1)
    }

    func testScoreStateValues() {
        XCTAssertEqual(ScoreState.unset.rawValue, "unset")
        XCTAssertEqual(ScoreState.scored.rawValue, "scored")
        XCTAssertEqual(ScoreState.na.rawValue, "na")
    }

    static var allTests = [
        ("testDecodeMediaPage", testDecodeMediaPage),
        ("testDecodeReviewItem", testDecodeReviewItem),
        ("testScoreStateValues", testScoreStateValues),
    ]
}
```

**Step 3: Write ImageDecoderTests.swift**

```swift
import XCTest
@testable import ComfyGalleryMobile

final class ImageDecoderTests: XCTestCase {
    func testDownsample() {
        // Create a simple test image
        let size = CGSize(width: 200, height: 300)
        let renderer = UIGraphicsImageRenderer(size: size)
        let image = renderer.image { ctx in
            UIColor.red.setFill()
            ctx.fill(CGRect(origin: .zero, size: size))
        }
        guard let data = image.pngData() else {
            XCTFail("Could not create test image data")
            return
        }

        let downsampled = ImageDecoder.downsample(data: data, to: CGSize(width: 100, height: 150))
        XCTAssertNotNil(downsampled)
        XCTAssertLessThanOrEqual(downsampled!.size.width, 100 * UIScreen.main.scale)
    }

    static var allTests = [
        ("testDownsample", testDownsample),
    ]
}
```

**Step 4: Write ReviewCommandQueueTests.swift**

```swift
import XCTest
@testable import ComfyGalleryMobile

final class ReviewCommandQueueTests: XCTestCase {
    // Tests would mock APIClient and LocalStore
    // For now, structural validation

    func testPendingMutationCreation() {
        let mutation = PendingMutation(
            localUUID: "test-uuid",
            serverProfileUUID: "profile-1",
            reviewSessionUUID: "session-1",
            mediaUUID: "media-1",
            evaluationUUID: "eval-1",
            criterionVersionUUID: "crit-1",
            commandKind: .score,
            intendedValue: 7,
            baseEvaluationVersion: 3
        )

        XCTAssertEqual(mutation.commandKind, .score)
        XCTAssertEqual(mutation.intendedValue, 7)
        XCTAssertEqual(mutation.baseEvaluationVersion, 3)
        XCTAssertEqual(mutation.attemptCount, 0)
    }

    func testCommandKinds() {
        let score = PendingMutation(
            serverProfileUUID: "p", reviewSessionUUID: "s", mediaUUID: "m",
            evaluationUUID: "e", commandKind: .score, baseEvaluationVersion: 1
        )
        XCTAssertEqual(score.commandKind, .score)

        let trash = PendingMutation(
            serverProfileUUID: "p", reviewSessionUUID: "s", mediaUUID: "m",
            evaluationUUID: "e", commandKind: .trash, baseEvaluationVersion: 1
        )
        XCTAssertEqual(trash.commandKind, .trash)
    }

    static var allTests = [
        ("testPendingMutationCreation", testPendingMutationCreation),
        ("testCommandKinds", testCommandKinds),
    ]
}
```

---

### Task 17: Tests — Fixture contract tests

**Files:**
- Create: `mobile/Fixtures/review_item_image.json`
- Create: `mobile/Fixtures/review_item_video.json`
- Create: `mobile/Fixtures/error_401.json`
- Create: `mobile/Fixtures/error_409.json`
- Create: `mobile/Fixtures/error_422.json`
- Create: `mobile/ComfyGalleryMobileTests/FixtureContractTests.swift`

**Step 1: Create sanitized fixtures**

Create `mobile/Fixtures/review_item_image.json`:
```json
{
  "session": {
    "id": "019f0000-0000-0000-0000-000000000001",
    "current_cursor": 0,
    "candidate_count": 10,
    "progress_counts": {
      "not_started": 8,
      "in_progress": 1,
      "complete": 1,
      "trash": 0
    }
  },
  "position": 0,
  "media": {
    "id": "019f0000-0000-0000-0000-000000000101",
    "kind": "image",
    "preview_url": "/api/v1/media/019f0000-0000-0000-0000-000000000101/preview",
    "playback_url": null,
    "width": 1024,
    "height": 1536,
    "duration_seconds": null
  },
  "prompts": [
    {
      "role": "positive",
      "label": "Prompt",
      "text": "A serene mountain landscape at golden hour with soft clouds."
    }
  ],
  "evaluations": [
    {
      "id": "019f0000-0000-0000-0000-000000000201",
      "evaluation_kind": "base",
      "progress_state": "not_started",
      "is_trash": false,
      "version": 1,
      "criteria": [
        {
          "id": "019f0000-0000-0000-0000-000000000301",
          "label": "Aesthetic appeal",
          "description": "Overall visual quality and beauty of the image",
          "min_value": 0,
          "max_value": 10
        },
        {
          "id": "019f0000-0000-0000-0000-000000000302",
          "label": "Prompt adherence",
          "description": "How well the image follows the prompt",
          "min_value": 0,
          "max_value": 10
        }
      ],
      "scores": []
    }
  ]
}
```

Create `mobile/Fixtures/review_item_video.json` (similar but kind: video with playback_url).

Create `mobile/Fixtures/error_401.json`:
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token",
    "details": {},
    "request_id": "req-error-401"
  }
}
```

Create `mobile/Fixtures/error_409.json`:
```json
{
  "error": {
    "code": "EVALUATION_VERSION_CONFLICT",
    "message": "The evaluation changed since it was loaded.",
    "details": {},
    "request_id": "req-error-409"
  }
}
```

Create `mobile/Fixtures/error_422.json`:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Score value must be between 0 and 10.",
    "details": {},
    "request_id": "req-error-422"
  }
}
```

**Step 2: Write FixtureContractTests.swift**

```swift
import XCTest
@testable import ComfyGalleryMobile

final class FixtureContractTests: XCTestCase {
    func testDecodeImageReviewItemFixture() throws {
        let url = Bundle(for: Self.self)
            .url(forResource: "review_item_image", withExtension: "json", subdirectory: "Fixtures")!
        let data = try Data(contentsOf: url)
        let item = try JSONDecoder().decode(ReviewItem.self, from: data)

        XCTAssertEqual(item.media.kind, .image)
        XCTAssertEqual(item.prompts.count, 1)
        XCTAssertEqual(item.evaluations.count, 1)
        XCTAssertEqual(item.evaluations[0].criteria.count, 2)
        XCTAssertEqual(item.evaluations[0].progressState, .notStarted)
        XCTAssertFalse(item.evaluations[0].isTrash)
    }

    func testDecodeError401Fixture() throws {
        let url = Bundle(for: Self.self)
            .url(forResource: "error_401", withExtension: "json", subdirectory: "Fixtures")!
        let data = try Data(contentsOf: url)
        let envelope = try JSONDecoder().decode(APIErrorEnvelope.self, from: data)

        XCTAssertEqual(envelope.error.code, "UNAUTHORIZED")
        XCTAssertEqual(envelope.error.requestId, "req-error-401")
    }

    func testDecodeError409Fixture() throws {
        let url = Bundle(for: Self.self)
            .url(forResource: "error_409", withExtension: "json", subdirectory: "Fixtures")!
        let data = try Data(contentsOf: url)
        let envelope = try JSONDecoder().decode(APIErrorEnvelope.self, from: data)

        XCTAssertEqual(envelope.error.code, "EVALUATION_VERSION_CONFLICT")
    }

    func testDecodeError422Fixture() throws {
        let url = Bundle(for: Self.self)
            .url(forResource: "error_422", withExtension: "json", subdirectory: "Fixtures")!
        let data = try Data(contentsOf: url)
        let envelope = try JSONDecoder().decode(APIErrorEnvelope.self, from: data)

        XCTAssertEqual(envelope.error.code, "VALIDATION_ERROR")
    }

    func testNoForbiddenMetadataInReviewItem() throws {
        let url = Bundle(for: Self.self)
            .url(forResource: "review_item_image", withExtension: "json", subdirectory: "Fixtures")!
        let data = try Data(contentsOf: url)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        let jsonString = String(data: data, encoding: .utf8) ?? ""
        let forbidden = ["filename", "sha256", "checkpoint", "lora", "workflow", "source_path", "model"]
        for term in forbidden {
            XCTAssertFalse(
                jsonString.lowercased().contains(term),
                "Fixture contains forbidden metadata: \(term)"
            )
        }
    }

    static var allTests = [
        ("testDecodeImageReviewItemFixture", testDecodeImageReviewItemFixture),
        ("testDecodeError401Fixture", testDecodeError401Fixture),
        ("testDecodeError409Fixture", testDecodeError409Fixture),
        ("testDecodeError422Fixture", testDecodeError422Fixture),
        ("testNoForbiddenMetadataInReviewItem", testNoForbiddenMetadataInReviewItem),
    ]
}
```

---

### Task 18: Tests — Integration tests

**Files:**
- Create: `mobile/ComfyGalleryMobileTests/IntegrationTests.swift`

**Step 1: Write IntegrationTests.swift**

```swift
import XCTest
@testable import ComfyGalleryMobile

final class IntegrationTests: XCTestCase {
    private var apiClient: APIClient!
    private var baseURL: URL!

    override func setUp() async throws {
        try await super.setUp()
        // Use local Docker environment
        baseURL = URL(string: ProcessInfo.processInfo.environment["TEST_BASE_URL"] ?? "http://localhost:8181")!
        let credentialStore = CredentialStore()
        apiClient = APIClient(credentialStore: credentialStore)
        await apiClient.configure(baseURL: baseURL)
    }

    func testHealthCheck() async throws {
        let health: Health = try await apiClient.request(.health)
        XCTAssertEqual(health.status, "ok")
    }

    func testAuthSessionWithInvalidToken() async throws {
        do {
            let _: UserSession = try await apiClient.request(.authSession)
            XCTFail("Expected unauthorized error")
        } catch let error as APIError {
            XCTAssertEqual(error, .unauthorized)
        }
    }

    // Additional integration tests would run against a real Docker backend
    // These are gated behind TEST_BASE_URL environment variable
}
```

---

### Task 19: Tests — UI tests

**Files:**
- Create: `mobile/ComfyGalleryMobileUITests/ComfyGalleryMobileUITests.swift`

**Step 1: Write ComfyGalleryMobileUITests.swift**

```swift
import XCTest

final class ComfyGalleryMobileUITests: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["UI-TESTING"]
        app.launch()
    }

    func testConnectionScreenAppears() {
        XCTAssertTrue(app.textFields["Server URL"].exists)
        XCTAssertTrue(app.buttons["Connect"].exists)
    }

    func testLibraryTabExists() {
        // After authentication mock
        let libraryTab = app.tabBars.buttons["Library"]
        XCTAssertTrue(libraryTab.waitForExistence(timeout: 5))
    }

    func testReviewTabExists() {
        let reviewTab = app.tabBars.buttons["Review"]
        XCTAssertTrue(reviewTab.waitForExistence(timeout: 5))
    }

    func testSettingsTabExists() {
        let settingsTab = app.tabBars.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: 5))
    }

    func testDynamicTypeSupport() {
        XCUIDevice.shared.press(.home)
        // Accessibility verification
        let app = XCUIApplication()
        app.launchArguments = ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryXXXL"]
        app.launch()
        XCTAssertTrue(app.exists)
    }
}
```

---

### Task 20: Xcode project configuration

**Files:**
- Create: `mobile/ComfyGalleryMobile/Resources/Info.plist`
- Create: `mobile/project.yml` (if using XcodeGen)

**Step 1: Write Info.plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>Comfy Gallery</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>NSLocalNetworkUsageDescription</key>
    <string>Connect to your self-hosted Comfy Gallery server on the local network.</string>
    <key>UIApplicationSceneManifest</key>
    <dict>
        <key>UIApplicationSupportsMultipleScenes</key>
        <false/>
    </dict>
    <key>UILaunchScreen</key>
    <dict/>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationLandscapeLeft</string>
        <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
    <key>UISupportedInterfaceOrientations~ipad</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationPortraitUpsideDown</string>
        <string>UIInterfaceOrientationLandscapeLeft</string>
        <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>armv7</string>
    </array>
    <key>UIStatusBarStyle</key>
    <string>UIStatusBarStyleDefault</string>
    <key>UIUserInterfaceStyle</key>
    <string>Automatic</string>
</dict>
</plist>
```

**Step 2: Generate the project**

Run: `cd mobile && swift package init --name ComfyGalleryMobile --type library`
Then manually create the Xcode project using `xcodebuild` or by hand-crafting the `.xcodeproj/project.pbxproj`.

For a practical CLI-only approach, use `swift package` to manage the project as an iOS-compatible Swift package, or create the `.xcodeproj` using `xcodegen spec`. If neither tool is available, provide instructions for opening the directory structure in Xcode and creating targets interactively.

---

## Build and Run

After all files are created:

```bash
cd mobile
# Option 1: If xcodegen is available
xcodegen generate

# Option 2: Open in Xcode
open ComfyGalleryMobile.xcodeproj
# or if no .xcodeproj exists, create one in Xcode and add all files

# Build
xcodebuild -project ComfyGalleryMobile.xcodeproj -scheme ComfyGalleryMobile -sdk iphoneos -destination 'generic/platform=iOS' build
```

---

## Implementation Order

1. Tasks 1-2: Project skeleton + app entry point
2. Tasks 3-4: API models + client
3. Task 5: Authentication
4. Task 6: Persistence
5. Tasks 7-8: Media pipeline + command queue
6. Task 9: Connection UI
7. Task 10: Library UI
8. Task 11: Viewer UI
9. Task 12: Review home UI
10. Task 13: Review workspace UI
11. Task 14: Settings UI
12. Task 15: Design system
13. Tasks 16-19: Tests
14. Task 20: Final project configuration
