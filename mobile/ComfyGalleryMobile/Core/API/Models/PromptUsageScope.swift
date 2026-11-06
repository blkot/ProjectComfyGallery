import Foundation

struct PromptUsageScope: Hashable, Sendable, Identifiable {
    let promptID: String
    var characterLora: String?
    var id: String { promptID + "|" + (characterLora ?? "") }

    var queryItems: [URLQueryItem] {
        var items = [URLQueryItem(name: "prompt_id", value: promptID)]
        if let characterLora, !characterLora.isEmpty { items.append(URLQueryItem(name: "character_lora", value: characterLora)) }
        return items
    }

    static func identifier(source: String, index: String) -> String? {
        let source = source.trimmingCharacters(in: .whitespacesAndNewlines)
        let index = index.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !source.isEmpty, !index.isEmpty, index.utf8.allSatisfy({ (48...57).contains($0) }) else { return nil }
        // Keep leading zeroes; the server owns canonical resolution.
        return "\(source) - \(index)"
    }
}
