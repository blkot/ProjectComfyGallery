import Foundation

struct DownloadedPayload: Sendable {
    let data: Data
    let mimeType: String?
    let expectedLength: Int64
    let requestID: String?
}

enum APIClientError: LocalizedError, Sendable, Equatable {
    case notConfigured
    case crossOriginResource
    case invalidResponse
    case invalidContentType
    case server(status: Int, code: String?, message: String, requestID: String?)
    case network

    var errorDescription: String? {
        switch self {
        case .notConfigured: "Connect to a gallery first."
        case .crossOriginResource: "The server returned a media URL on a different origin."
        case .invalidResponse: "The gallery returned an invalid response."
        case .invalidContentType: "The gallery returned an unsupported media type."
        case .server(let status, _, let message, _):
            status == 401 ? "The API token is no longer valid." : message
        case .network: "The gallery could not be reached."
        }
    }

    var requiresAuthentication: Bool {
        if case .server(let status, _, _, _) = self {
            return status == 401 || status == 403
        }
        return false
    }
}

actor APIClient {
    private struct Configuration: Sendable {
        let profile: ServerProfile
        let token: String
    }

    private let session: URLSession
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()
    private var configuration: Configuration?

    init(session: URLSession = APIClient.makeSession()) {
        self.session = session
    }

    func validate(baseURL: URL, token: String) async throws -> (Health, AuthenticatedUser) {
        let health = try await checkHealth(baseURL: baseURL)
        let user = try await authenticate(baseURL: baseURL, token: token)
        return (health, user)
    }

    func checkHealth(baseURL: URL) async throws -> Health {
        try await request(
            Health.self,
            baseURL: baseURL,
            path: "/health/live",
            token: nil
        )
    }

    func authenticate(baseURL: URL, token: String) async throws -> AuthenticatedUser {
        let authenticated: AuthenticatedSession = try await request(
            AuthenticatedSession.self,
            baseURL: baseURL,
            path: "/api/v1/auth/session",
            token: token
        )
        return authenticated.user
    }

    func configure(profile: ServerProfile, token: String) {
        configuration = Configuration(profile: profile, token: token)
    }

    func clearConfiguration() {
        configuration = nil
    }

    func get<T: Decodable & Sendable>(
        _ type: T.Type,
        path: String,
        queryItems: [URLQueryItem] = []
    ) async throws -> T {
        guard let configuration else { throw APIClientError.notConfigured }
        return try await request(
            type,
            baseURL: configuration.profile.baseURL,
            path: path,
            queryItems: queryItems,
            token: configuration.token
        )
    }

    func put<Response: Decodable & Sendable, Body: Encodable & Sendable>(
        _ responseType: Response.Type,
        path: String,
        body: Body
    ) async throws -> Response {
        guard let configuration else { throw APIClientError.notConfigured }
        let encodedBody: Data
        do {
            encodedBody = try encoder.encode(body)
        } catch {
            throw APIClientError.invalidResponse
        }
        return try await request(
            responseType,
            baseURL: configuration.profile.baseURL,
            path: path,
            token: configuration.token,
            method: "PUT",
            body: encodedBody
        )
    }

    func download(path: String) async throws -> DownloadedPayload {
        guard let configuration else { throw APIClientError.notConfigured }
        let url = try resolve(
            path: path,
            against: configuration.profile.baseURL,
            queryItems: []
        )
        var request = URLRequest(url: url)
        request.timeoutInterval = 60
        request.setValue("Bearer \(configuration.token)", forHTTPHeaderField: "Authorization")

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch is CancellationError {
            throw CancellationError()
        } catch {
            throw APIClientError.network
        }
        let http = try validatedHTTPResponse(response, data: data)
        return DownloadedPayload(
            data: data,
            mimeType: http.mimeType,
            expectedLength: http.expectedContentLength,
            requestID: http.value(forHTTPHeaderField: "X-Request-ID")
        )
    }

    private func request<T: Decodable & Sendable>(
        _ type: T.Type,
        baseURL: URL,
        path: String,
        queryItems: [URLQueryItem] = [],
        token: String?,
        method: String = "GET",
        body: Data? = nil
    ) async throws -> T {
        let url = try resolve(path: path, against: baseURL, queryItems: queryItems)
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch is CancellationError {
            throw CancellationError()
        } catch {
            throw APIClientError.network
        }
        _ = try validatedHTTPResponse(response, data: data)
        do {
            return try decoder.decode(type, from: data)
        } catch {
            throw APIClientError.invalidResponse
        }
    }

    private func resolve(
        path: String,
        against baseURL: URL,
        queryItems: [URLQueryItem]
    ) throws -> URL {
        let candidate: URL
        if let absolute = URL(string: path), absolute.scheme != nil {
            candidate = absolute
        } else {
            guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
                throw APIClientError.invalidResponse
            }
            components.path = path.hasPrefix("/") ? path : "/\(path)"
            components.queryItems = queryItems.isEmpty ? nil : queryItems
            guard let resolved = components.url else {
                throw APIClientError.invalidResponse
            }
            candidate = resolved
        }
        guard BaseURLNormalizer.isSameOrigin(candidate, baseURL) else {
            throw APIClientError.crossOriginResource
        }
        return candidate
    }

    private func validatedHTTPResponse(_ response: URLResponse, data: Data) throws -> HTTPURLResponse {
        guard let http = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard 200..<300 ~= http.statusCode else {
            let envelope = try? decoder.decode(APIErrorEnvelope.self, from: data)
            throw APIClientError.server(
                status: http.statusCode,
                code: envelope?.error.code,
                message: envelope?.error.message ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode),
                requestID: envelope?.error.requestID ?? http.value(forHTTPHeaderField: "X-Request-ID")
            )
        }
        return http
    }

    nonisolated static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpMaximumConnectionsPerHost = 6
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 120
        return URLSession(configuration: configuration)
    }
}
