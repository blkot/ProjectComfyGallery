import Foundation

enum BaseURLValidationError: LocalizedError, Equatable {
    case empty
    case invalid
    case unsupportedScheme
    case missingHost
    case containsCredentials
    case containsQueryOrFragment

    var errorDescription: String? {
        switch self {
        case .empty: "Enter the gallery URL."
        case .invalid: "The gallery URL is invalid."
        case .unsupportedScheme: "Use an HTTP or HTTPS gallery URL."
        case .missingHost: "The gallery URL must include a host."
        case .containsCredentials: "Do not include credentials in the gallery URL."
        case .containsQueryOrFragment: "Remove the query or fragment from the gallery URL."
        }
    }
}
enum BaseURLNormalizer {
    static func normalize(_ rawValue: String) throws -> URL {
        let trimmed = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { throw BaseURLValidationError.empty }
        guard var components = URLComponents(string: trimmed) else {
            throw BaseURLValidationError.invalid
        }
        guard let scheme = components.scheme?.lowercased(), ["http", "https"].contains(scheme) else {
            throw BaseURLValidationError.unsupportedScheme
        }
        guard let host = components.host, !host.isEmpty else {
            throw BaseURLValidationError.missingHost
        }
        guard components.user == nil, components.password == nil else {
            throw BaseURLValidationError.containsCredentials
        }
        guard components.query == nil, components.fragment == nil else {
            throw BaseURLValidationError.containsQueryOrFragment
        }

        components.scheme = scheme
        components.host = host.lowercased()
        components.path = "/"
        components.query = nil
        components.fragment = nil

        guard let url = components.url else { throw BaseURLValidationError.invalid }
        return url
    }

    static func isSameOrigin(_ lhs: URL, _ rhs: URL) -> Bool {
        lhs.scheme?.lowercased() == rhs.scheme?.lowercased()
            && lhs.host?.lowercased() == rhs.host?.lowercased()
            && effectivePort(lhs) == effectivePort(rhs)
    }

    private static func effectivePort(_ url: URL) -> Int? {
        if let port = url.port { return port }
        switch url.scheme?.lowercased() {
        case "http": return 80
        case "https": return 443
        default: return nil
        }
    }
}
