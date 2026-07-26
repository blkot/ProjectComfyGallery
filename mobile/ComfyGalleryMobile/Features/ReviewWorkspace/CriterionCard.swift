import SwiftUI

struct CriterionCard: View {
    let criterion: Criterion
    let score: EvaluationScore?
    let evaluation: Evaluation
    let onScore: (Int) -> Void
    let onClear: () -> Void
    let onNA: () -> Void
    let isDisabled: Bool

    @State private var sliderValue: Double = 0
    @State private var isEditing = false
    @State private var pendingFinalValue: Int?

    private var isUnset: Bool {
        guard let score = score else { return true }
        return score.state != .scored
    }

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
                HStack {
                    Slider(
                        value: Binding(
                            get: { sliderValue },
                            set: { newValue in
                                let intValue = Int(newValue.rounded())
                                let oldValue = Int(sliderValue.rounded())
                                if intValue != oldValue {
                                    let generator = UISelectionFeedbackGenerator()
                                    generator.selectionChanged()
                                }
                                sliderValue = Double(intValue)
                                if isEditing {
                                    pendingFinalValue = intValue
                                }
                            }
                        ),
                        in: 0...10,
                        step: 1,
                        onEditingChanged: { editing in
                            isEditing = editing
                            if !editing {
                                guard let final = pendingFinalValue else { return }
                                pendingFinalValue = nil
                                let currentDisplayed = displayedScoreValue()
                                guard final != currentDisplayed else { return }
                                onScore(final)
                            }
                        }
                    )
                    .disabled(isDisabled)
                    .opacity(isUnset ? 0.4 : 1.0)

                    Text("\(Int(sliderValue.rounded()))")
                        .font(.title3).fontWeight(.semibold)
                        .monospacedDigit()
                        .frame(minWidth: 32, alignment: .trailing)
                        .foregroundStyle(isUnset ? .secondary : .primary)
                }

                HStack {
                    Text("0").font(.caption2).foregroundStyle(.secondary)
                    Spacer()
                    Text("5").font(.caption2).foregroundStyle(.secondary)
                    Spacer()
                    Text("10").font(.caption2).foregroundStyle(.secondary)
                }
            }
            .onAppear { syncSliderFromScore() }
            .onChange(of: score?.value) { _, _ in
                if !isEditing { syncSliderFromScore() }
            }
            .onChange(of: score?.state) { _, _ in
                if !isEditing { syncSliderFromScore() }
            }

            HStack(spacing: 12) {
                Button {
                    onClear()
                } label: {
                    Label("Clear", systemImage: "xmark").font(.caption)
                }
                .buttonStyle(.bordered)
                .disabled(isDisabled || isUnset)

                Spacer()

                Button {
                    onNA()
                } label: {
                    Label("N/A", systemImage: "nosign").font(.caption)
                }
                .buttonStyle(.bordered)
                .disabled(isDisabled || (score?.state == .na))
                .tint(.orange)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func syncSliderFromScore() {
        if let score = score, score.state == .scored, let value = score.value {
            sliderValue = Double(value)
        } else {
            sliderValue = 0
        }
    }

    private func displayedScoreValue() -> Int? {
        guard let score = score, score.state == .scored else { return nil }
        return score.value
    }

    @ViewBuilder
    private var scoreStateChip: some View {
        if let score = score {
            switch score.state {
            case .scored:
                if let value = score.value {
                    Text("\(value) / 10").font(.caption)
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(.tint.opacity(0.15)).foregroundStyle(.tint).clipShape(Capsule())
                } else {
                    Text("—").font(.caption).foregroundStyle(.secondary)
                }
            case .na:
                Text("N/A").font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(.orange.opacity(0.15)).foregroundStyle(.orange).clipShape(Capsule())
            case .unset:
                Text("Unset").font(.caption).foregroundStyle(.secondary)
            }
        } else {
            Text("Unset").font(.caption).foregroundStyle(.secondary)
        }
    }
}
