import Foundation

struct MediaDaySection: Identifiable, Sendable {
    let id: String
    let title: String
    var items: [MobileMediaSummary]

    static func group(_ items: [MobileMediaSummary], sort: GalleryScope.Sort, byCharacter: Bool = false) -> [MediaDaySection] {
        var sections: [MediaDaySection] = []
        var previousDay: String?
        for item in items {
            let timestamp = sort == .importedNewest ? item.createdAt : item.fileCreatedAt
            // Preserve the server's ordered records and source calendar dates.
            let character = item.characterLora?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let day = byCharacter ? (character.isEmpty ? "未定义角色" : character) : (timestamp.map { String($0.prefix(10)) } ?? "日期未知")
            let key = byCharacter ? day.lowercased() : day
            if key == previousDay, !sections.isEmpty {
                sections[sections.count - 1].items.append(item)
            } else {
                sections.append(MediaDaySection(id: item.id, title: day, items: [item]))
                previousDay = key
            }
        }
        return sections
    }
}
