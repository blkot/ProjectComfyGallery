import Foundation

enum APIError: Error, LocalizedError, Equatable {
    case unauthorized
    case forbidden
    case notFound
    case conflict(APIErrorEnvelope)
    case validationError(APIErrorEnvelope)
    case rateLimited
    case serverError(Int)
    case networkError(String)
    case decodingError(String)
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
        case .networkError(let message):
            return "Network error: \(message)"
        case .decodingError(let message):
            return "Unexpected server response format: \(message)"
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

    static func == (lhs: APIError, rhs: APIError) -> Bool {
        switch (lhs, rhs) {
        case (.unauthorized, .unauthorized),
             (.forbidden, .forbidden),
             (.notFound, .notFound),
             (.rateLimited, .rateLimited),
             (.invalidURL, .invalidURL),
             (.invalidResponse, .invalidResponse):
            return true
        case (.serverError(let a), .serverError(let b)):
            return a == b
        case (.networkError(let a), .networkError(let b)):
            return a == b
        case (.decodingError(let a), .decodingError(let b)):
            return a == b
        case (.conflict(let a), .conflict(let b)):
            return a.error.code == b.error.code
        case (.validationError(let a), .validationError(let b)):
            return a.error.code == b.error.code
        default:
            return false
        }
    }
}
