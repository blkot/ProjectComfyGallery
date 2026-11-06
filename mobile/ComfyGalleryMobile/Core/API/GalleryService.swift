import Foundation

protocol GalleryService: Sendable {
    func page(scope: GalleryScope, limit: Int, offset: Int) async throws -> MediaPage
    func detail(id: String) async throws -> MobileMediaSummary
    func navigation(id: String, scope: GalleryScope) async throws -> MediaNavigation
    func setFavorite(ids: [String], value: Bool) async throws -> MediaBulkResult
    func setTrash(ids: [String], value: Bool) async throws -> MediaBulkResult
    func setContentRating(id: String, rating: String) async throws
}

extension GalleryService {
    func setContentRating(id: String, rating: String) async throws { throw APIError.invalidResponse }
}
