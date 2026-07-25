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
