import Foundation

struct UserSession: Decodable, Sendable {
    let user: UserInfo

    struct UserInfo: Decodable, Sendable {
        let id: String
        let username: String
    }
}
