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
        config.timeoutIntervalForRequest = 10
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
        let data: Data = try await performRequest(endpoint)
        let decoder = JSONDecoder()
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            logger.error("Decoding error for \(endpoint.path): \(error.localizedDescription)")
            throw APIError.decodingError(error.localizedDescription)
        }
    }

    func requestData(_ endpoint: Endpoint) async throws -> Data {
        return try await performRequest(endpoint)
    }

    func download(_ endpoint: Endpoint, to destination: URL) async throws {
        let request = try await buildRequest(for: endpoint)
        let (tempURL, response) = try await session.download(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        try validateResponse(httpResponse, data: Data())
        if FileManager.default.fileExists(atPath: destination.path) {
            try FileManager.default.removeItem(at: destination)
        }
        try FileManager.default.moveItem(at: tempURL, to: destination)
    }

    private func performRequest(_ endpoint: Endpoint) async throws -> Data {
        let request = try await buildRequest(for: endpoint)
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        try validateResponse(httpResponse, data: data)
        return data
    }

    private func buildRequest(for endpoint: Endpoint) async throws -> URLRequest {
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
