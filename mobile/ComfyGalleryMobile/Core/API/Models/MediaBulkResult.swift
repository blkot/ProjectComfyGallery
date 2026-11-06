import Foundation

struct MediaBulkResult: Decodable, Sendable {
    let requestedCount: Int
    let updatedCount: Int
    let skippedCount: Int
    let errors: [String]

    var message: String {
        var text = "已更新 \(updatedCount) 项"
        if skippedCount > 0 { text += "，跳过 \(skippedCount) 项" }
        if !errors.isEmpty { text += "；\(errors.count) 项出错，请刷新后重试" }
        return text
    }

    enum CodingKeys: String, CodingKey {
        case requestedCount = "requested_count", updatedCount = "updated_count"
        case skippedCount = "skipped_count", errors
    }
}
