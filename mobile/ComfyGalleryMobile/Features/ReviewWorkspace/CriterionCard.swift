import SwiftUI

struct CriterionCard: View {
    let criterion: Criterion
    let score: EvaluationScore?
    let evaluation: Evaluation
    let onScore: (Int) -> Void
    let onClear: () -> Void
    let onNA: () -> Void
    let isDisabled: Bool

    @State private var sliderValue: Double = -1

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(criterion.label).font(.headline)
                Spacer()
                scoreStateChip
            }

            if let description = criterion.description {
                Text(description).font(.caption).foregroundStyle(.secondary)
            }

            VStack(spacing: 8) {
                Slider(value: Binding(
                    get: { sliderValue },
                    set: { newValue in
                        let intValue = Int(newValue.rounded())
                        if intValue != Int(sliderValue.rounded()) {
                            let generator = UISelectionFeedbackGenerator()
                            generator.selectionChanged()
                        }
                        sliderValue = Double(intValue)
                    }
                ), in: -1...10, step: 1)
                .disabled(isDisabled)

                HStack {
                    Text("0").font(.caption2).foregroundStyle(.secondary)
                    Spacer()
                    Text("5").font(.caption2).foregroundStyle(.secondary)
                    Spacer()
                    Text("10").font(.caption2).foregroundStyle(.secondary)
                }
            }
            .onAppear {
                if let score = score, score.state == .scored, let value = score.value {
                    sliderValue = Double(value)
                } else { sliderValue = -1 }
            }
            .onChange(of: sliderValue) { _, newValue in
                let intValue = Int(newValue.rounded())
                if intValue >= 0 { onScore(intValue) }
            }

            HStack(spacing: 12) {
                Button { sliderValue = -1; onClear() } label: {
                    Label("Clear", systemImage: "xmark").font(.caption)
                }
                .buttonStyle(.bordered).disabled(isDisabled)
                Spacer()
                Button { onNA() } label: {
                    Label("N/A", systemImage: "nosign").font(.caption)
                }
                .buttonStyle(.bordered).disabled(isDisabled)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var scoreStateChip: some View {
        if let score = score {
            switch score.state {
            case .scored:
                Text("\(score.value ?? -1) / 10").font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(.tint.opacity(0.15)).foregroundStyle(.tint).clipShape(Capsule())
            case .na:
                Text("N/A").font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(.orange.opacity(0.15)).foregroundStyle(.orange).clipShape(Capsule())
            case .unset:
                Text("—").font(.caption).foregroundStyle(.secondary)
            }
        } else {
            Text("—").font(.caption).foregroundStyle(.secondary)
        }
    }
}
