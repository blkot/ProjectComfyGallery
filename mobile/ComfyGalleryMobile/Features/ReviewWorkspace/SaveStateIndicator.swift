import SwiftUI

struct SaveStateIndicator: View {
    let state: ReviewWorkspaceFeature.SaveState
    var onTap: (() -> Void)? = nil

    var body: some View {
        Group {
            if state == .needsAttention, let onTap = onTap {
                Button(action: onTap) {
                    content
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Save needs attention. Tap for details.")
            } else {
                content
            }
        }
        .font(.caption)
    }

    @ViewBuilder
    private var content: some View {
        HStack(spacing: 4) {
            switch state {
            case .saved:
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                Text("Saved").foregroundStyle(.secondary)
            case .saving:
                ProgressView().scaleEffect(0.7)
                Text("Saving…").foregroundStyle(.secondary)
            case .savedLocally:
                Image(systemName: "arrow.down.circle.fill").foregroundStyle(.orange)
                Text("Saved locally").foregroundStyle(.secondary)
            case .needsAttention:
                Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.red)
                Text("Needs attention").foregroundStyle(.red)
            }
        }
    }
}
