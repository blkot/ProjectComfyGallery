import SwiftUI

struct PromptSection: View {
    let prompts: [ReviewPrompt]
    @State private var expandedPromptIndex: Int? = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if prompts.isEmpty {
                Text("No prompt was extracted for this media.")
                    .font(.subheadline).foregroundStyle(.secondary)
            } else {
                ForEach(Array(prompts.enumerated()), id: \.offset) { index, prompt in
                    VStack(alignment: .leading, spacing: 4) {
                        Button {
                            withAnimation { expandedPromptIndex = expandedPromptIndex == index ? nil : index }
                        } label: {
                            HStack {
                                Text(prompt.label).font(.subheadline).fontWeight(.medium)
                                Spacer()
                                Image(systemName: expandedPromptIndex == index ? "chevron.up" : "chevron.down").font(.caption)
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)

                        if expandedPromptIndex == index {
                            Text(prompt.text).font(.body).textSelection(.enabled).padding(.top, 4)
                        } else if prompt.text.count > 200 {
                            Text(String(prompt.text.prefix(200)) + "...")
                                .font(.body).lineLimit(3).padding(.top, 4)
                            Button("Show More") { withAnimation { expandedPromptIndex = index } }.font(.caption)
                        }
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }
}
