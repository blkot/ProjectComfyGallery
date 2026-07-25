import SwiftUI

struct SaveStateIndicator: View {
    let state: ReviewWorkspaceFeature.SaveState

    var body: some View {
        HStack(spacing: 4) {
            switch state {
            case .saved:
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                Text("Saved").foregroundStyle(.secondary)
            case .saving:
                ProgressView().scaleEffect(0.7)
                Text("Saving...").foregroundStyle(.secondary)
            case .savedLocally:
                Image(systemName: "arrow.down.circle.fill").foregroundStyle(.orange)
                Text("Saved locally").foregroundStyle(.secondary)
            case .needsAttention:
                Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.red)
                Text("Needs attention").foregroundStyle(.red)
            }
        }
        .font(.caption)
    }
}
