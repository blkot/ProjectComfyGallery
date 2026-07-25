import SwiftUI

struct FilterSheet: View {
    @Binding var kind: MediaKind?
    @Binding var evaluationState: EvaluationState?
    @Binding var trash: LibraryFeature.FilterTrashOption
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Media Type") {
                    Button("All") { kind = nil }
                        .foregroundStyle(kind == nil ? .tint : .primary)
                    Button("Images") { kind = .image }
                        .foregroundStyle(kind == .image ? .tint : .primary)
                    Button("Videos") { kind = .video }
                        .foregroundStyle(kind == .video ? .tint : .primary)
                }

                Section("Evaluation Status") {
                    Button("All") { evaluationState = nil }
                        .foregroundStyle(evaluationState == nil ? .tint : .primary)
                    Button("Not Started") { evaluationState = .notStarted }
                        .foregroundStyle(evaluationState == .notStarted ? .tint : .primary)
                    Button("In Progress") { evaluationState = .inProgress }
                        .foregroundStyle(evaluationState == .inProgress ? .tint : .primary)
                    Button("Complete") { evaluationState = .complete }
                        .foregroundStyle(evaluationState == .complete ? .tint : .primary)
                }

                Section("Trash") {
                    ForEach(LibraryFeature.FilterTrashOption.allCases, id: \.self) { option in
                        Button(option.label) { trash = option }
                            .foregroundStyle(trash == option ? .tint : .primary)
                    }
                }
            }
            .navigationTitle("Filters")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
