import Foundation

struct LiveGalleryService: GalleryService {
    let apiClient: APIClient

    func page(scope: GalleryScope, limit: Int, offset: Int) async throws -> MediaPage {
        if let prompt = scope.promptUsage {
            let result: PromptRegistryLookup = try await apiClient.request(.promptLookup(scope: prompt, limit: limit, offset: offset))
            return MediaPage(items: result.media, total: result.totalMedia, limit: result.limit, offset: result.offset)
        }
        let page: MediaPage = try await apiClient.request(.galleryList(scope: scope, limit: limit, offset: offset))
        if let character = scope.characterLora, !character.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
           page.characterLora != character.trimmingCharacters(in: .whitespacesAndNewlines) {
            throw NSError(domain: "GalleryCompatibility", code: 1, userInfo: [NSLocalizedDescriptionKey: "服务器尚未支持精确 Character LoRA 筛选，请更新后端。未展示未筛选的结果。"])
        }
        if (scope.classifierStatus != nil || scope.classifierRating != nil),
           page.items.contains(where: {
               !ClassifierProjection.matches(
                   status: scope.classifierStatus,
                   rating: scope.classifierRating,
                   assessment: $0.mediaSafetyAssessment,
                   review: $0.mediaSafetyReview
               )
           }) {
            throw NSError(domain: "GalleryCompatibility", code: 2, userInfo: [NSLocalizedDescriptionKey: "服务器返回了不符合 classifier 筛选的照片。请更新后端；未展示未筛选结果。"])
        }
        return page
    }

    func detail(id: String) async throws -> MobileMediaSummary {
        try await apiClient.request(.mediaDetail(id: id))
    }

    func navigation(id: String, scope: GalleryScope) async throws -> MediaNavigation {
        if let prompt = scope.promptUsage { return try await apiClient.request(.promptNavigation(id: id, scope: prompt)) }
        return try await apiClient.request(.mediaNavigation(id: id, scope: scope))
    }

    func setFavorite(ids: [String], value: Bool) async throws -> MediaBulkResult {
        try await apiClient.request(.bulkFavorite(ids: ids, value: value))
    }

    func setTrash(ids: [String], value: Bool) async throws -> MediaBulkResult {
        try await apiClient.request(.bulkTrash(ids: ids, value: value))
    }

    func setContentRating(id: String, rating: String) async throws {
        _ = try await apiClient.requestData(.setContentRating(id: id, rating: rating))
    }
}
