import Foundation

/// One scope is shared by the grid, pagination, and server-side viewer navigation.
struct GalleryScope: Hashable, Sendable {
    var kind: MediaKind?
    var favorite: Favorite = .all
    var trash: Trash = .hidden
    var rating: Rating = .all
    var sort: Sort = .importedNewest
    var query = ""
    var characterLora: String?
    var promptUsage: PromptUsageScope?
    var classifierStatus: ClassifierStatus?
    var classifierRating: ClassifierRating?

    enum Favorite: String, CaseIterable, Sendable {
        case all = "全部", only = "仅收藏", excluded = "未收藏"
    }

    enum Trash: String, CaseIterable, Sendable {
        case hidden = "正常图库", only = "废纸篓", included = "包含废纸篓"
    }

    enum Rating: String, CaseIterable, Sendable {
        case all = "全部", sfw = "SFW", nsfw = "NSFW"
    }

    enum Sort: String, CaseIterable, Sendable {
        case importedNewest = "imported_desc"
        case fileNewest = "file_created_desc"
        case fileOldest = "file_created_asc"

        var label: String {
            switch self {
            case .importedNewest: "最近导入"
            case .fileNewest: "文件日期：由新到旧"
            case .fileOldest: "文件日期：由旧到新"
            }
        }
    }

    var queryItems: [URLQueryItem] {
        var items = [URLQueryItem(name: "sort", value: sort.rawValue)]
        if let kind { items.append(URLQueryItem(name: "kind", value: kind.rawValue)) }
        if let characterLora, !characterLora.isEmpty { items.append(URLQueryItem(name: "character_lora", value: characterLora)) }
        if favorite != .all {
            items.append(URLQueryItem(name: "favorite", value: String(favorite == .only)))
        }
        if trash != .included {
            items.append(URLQueryItem(name: "trash", value: String(trash == .only)))
        }
        if rating != .all {
            items.append(URLQueryItem(name: "content_rating", value: rating.rawValue.lowercased()))
        }
        if let classifierStatus {
            items.append(URLQueryItem(name: "classifier_status", value: classifierStatus.rawValue))
        }
        if let classifierRating {
            items.append(URLQueryItem(name: "classifier_rating", value: classifierRating.rawValue))
        }
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty { items.append(URLQueryItem(name: "q", value: trimmed)) }
        return items
    }

    var hasFilters: Bool {
        kind != nil || favorite != .all || rating != .all || characterLora != nil ||
            classifierStatus != nil || classifierRating != nil
    }

    /// Only local, mutable membership facts. Character/search membership remains server-owned.
    func excludes(_ item: MobileMediaSummary) -> Bool {
        guard promptUsage == nil else { return false }
        return (favorite == .only && item.favorite != true) ||
            (favorite == .excluded && item.favorite == true) ||
            (trash == .hidden && item.isTrash == true) ||
            (trash == .only && item.isTrash != true) ||
            (rating != .all && item.contentRating != rating.rawValue.lowercased()) ||
            !ClassifierProjection.matches(
                status: classifierStatus,
                rating: classifierRating,
                assessment: item.mediaSafetyAssessment,
                review: item.mediaSafetyReview
            )
    }
}
