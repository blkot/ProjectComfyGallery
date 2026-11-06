import Foundation

struct MediaWorkflowSummary: Decodable, Sendable {
    let displayFields: [String: Field]?
    var promptID: String? { displayFields?["prompt_id"]?.text }
    var characterLora: String? { displayFields?["character_lora"]?.text }
    var loras: [String] { displayFields?["lora_list"]?.loras ?? [] }

    struct Field: Decodable, Sendable {
        let text: String?
        let loras: [String]
        enum CodingKeys: String, CodingKey { case value }
        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            text = try? container.decode(String.self, forKey: .value)
            if let entries = try? container.decode([Lora].self, forKey: .value) { loras = entries.map(\.description) }
            else { loras = [] }
        }
    }

    private struct Lora: Decodable, Sendable {
        let description: String
        init(from decoder: Decoder) throws {
            var values = try decoder.unkeyedContainer()
            let name = try values.decode(String.self)
            let model = try values.decode(Double.self)
            let clip = try values.decode(Double.self)
            description = "\(name) · \(model.formatted()) / \(clip.formatted())"
        }
    }
    enum CodingKeys: String, CodingKey { case displayFields = "display_fields" }
}
