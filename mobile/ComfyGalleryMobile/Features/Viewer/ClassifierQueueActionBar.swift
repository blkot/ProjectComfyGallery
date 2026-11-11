import SwiftUI

struct ClassifierQueueActionBar: View {
    let position: Int
    let total: Int
    let sourceTotal: Int
    let truncated: Bool
    let disabled: Bool
    let selectedRating: ClassifierRating?
    let previous: () -> Void
    let rate: (ClassifierRating) -> Void
    let next: () -> Void
    let finish: () -> Void

    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                ForEach(ClassifierRating.allCases.filter(\.isHumanRating), id: \.self) { rating in
                    Button {
                        rate(rating)
                    } label: {
                        Label(rating.title, systemImage: rating.symbol)
                            .labelStyle(.titleAndIcon)
                            .font(.caption.weight(selectedRating == rating ? .semibold : .regular))
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.bordered)
                    .tint(selectedRating == rating ? .accentColor : .secondary)
                    .disabled(disabled)
                    .accessibilityValue(selectedRating == rating ? "当前生效" : "")
                }
            }
            HStack {
                Button("上一张", systemImage: "chevron.left", action: previous)
                    .disabled(disabled || position <= 1)
                Spacer()
                Text("\(position) / \(total)\(truncated ? " · 共 \(sourceTotal)" : "") · 不自动跳转")
                    .font(.footnote).foregroundStyle(.secondary).monospacedDigit()
                Spacer()
                if position >= total {
                    Button("完成复核", systemImage: "checkmark", action: finish)
                        .disabled(disabled)
                } else {
                    Button("下一张", systemImage: "chevron.right", action: next)
                        .labelStyle(.titleAndIcon)
                        .disabled(disabled)
                }
            }
            .frame(minHeight: 40)
        }
        .padding(.horizontal, 10).padding(.top, 8).padding(.bottom, 4)
        .background(.regularMaterial)
    }
}
