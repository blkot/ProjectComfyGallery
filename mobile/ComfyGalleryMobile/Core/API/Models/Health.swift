import Foundation

struct Health: Decodable, Sendable {
    let status: String
    let service: String?
    let version: String?
    let checks: [String: String]?
}
