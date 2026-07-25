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
