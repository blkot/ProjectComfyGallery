import Foundation

/// Anchor descriptions for each known review criterion, sourced from
/// doc/design/evaluation.md (V1 criterion catalog). Used to show what
/// 0 / 5 / 10 mean for each criterion underneath the title.
struct CriterionCatalog {
    struct Entry {
        let stableID: String
        let label: String
        let zeroAnchor: String
        let fiveAnchor: String
        let tenAnchor: String
    }

    static let entries: [Entry] = [
        // Universal core
        .init(stableID: "core.aesthetic_appeal",
              label: "Aesthetic appeal",
              zeroAnchor: "Unappealing or unusable",
              fiveAnchor: "Mixed or ordinary appeal",
              tenAnchor: "Exceptionally compelling"),
        .init(stableID: "core.composition",
              label: "Composition",
              zeroAnchor: "Failed or chaotic framing",
              fiveAnchor: "Readable with noticeable issues",
              tenAnchor: "Deliberate and highly effective"),
        .init(stableID: "core.prompt_adherence",
              label: "Prompt adherence",
              zeroAnchor: "Misses or contradicts the central request",
              fiveAnchor: "Captures the main idea but misses important details",
              tenAnchor: "Strongly fulfills the explicit intent"),
        .init(stableID: "core.logical_plausibility",
              label: "Logical plausibility",
              zeroAnchor: "Fundamentally incoherent",
              fiveAnchor: "Understandable with notable logic problems",
              tenAnchor: "Internally consistent within the intended style"),
        .init(stableID: "core.technical_execution",
              label: "Technical execution",
              zeroAnchor: "Severely degraded",
              fiveAnchor: "Serviceable with visible quality issues",
              tenAnchor: "Highly controlled and well finished"),
        .init(stableID: "core.artifact_cleanliness",
              label: "Artifact cleanliness",
              zeroAnchor: "Dominated by generation defects",
              fiveAnchor: "Some noticeable localized artifacts",
              tenAnchor: "No meaningful visible defects"),

        // Video module
        .init(stableID: "video.temporal_consistency",
              label: "Temporal consistency",
              zeroAnchor: "Persistent flicker or identity collapse",
              fiveAnchor: "Mostly stable with noticeable drift",
              tenAnchor: "Consistently stable"),
        .init(stableID: "video.motion_quality",
              label: "Motion quality",
              zeroAnchor: "Broken or unusable motion",
              fiveAnchor: "Recognizable but stiff or irregular",
              tenAnchor: "Smooth, natural, and purposeful"),
        .init(stableID: "video.sequence_coherence",
              label: "Sequence coherence",
              zeroAnchor: "Inexplicable progression",
              fiveAnchor: "Readable action with discontinuities",
              tenAnchor: "Logically continuous progression"),

        // Character module
        .init(stableID: "character.identity_fidelity",
              label: "Identity fidelity",
              zeroAnchor: "Target identity is unrecognizable",
              fiveAnchor: "Partial resemblance",
              tenAnchor: "Strongly matches defining traits"),
        .init(stableID: "character.identity_adaptability",
              label: "Identity adaptability",
              zeroAnchor: "Variation destroys identity or is ignored",
              fiveAnchor: "Partial balance",
              tenAnchor: "Requested variation succeeds while identity remains intact"),
    ]

    private static let byStableID: [String: Entry] = {
        Dictionary(uniqueKeysWithValues: entries.map { ($0.stableID, $0) })
    }()

    private static let byLabel: [String: Entry] = {
        Dictionary(uniqueKeysWithValues: entries.map { ($0.label.lowercased(), $0) })
    }()

    static func entry(forStableID stableID: String?) -> Entry? {
        guard let id = stableID, !id.isEmpty else { return nil }
        return byStableID[id]
    }

    static func entry(forLabel label: String?) -> Entry? {
        guard let label = label, !label.isEmpty else { return nil }
        return byLabel[label.lowercased()]
    }

    static func entry(for criterion: Criterion) -> Entry? {
        // Try the criterion's stable_id field first (if decoded), then
        // fall back to label matching.
        if let id = criterion.stableID, let e = entry(forStableID: id) {
            return e
        }
        return entry(forLabel: criterion.label)
    }
}
