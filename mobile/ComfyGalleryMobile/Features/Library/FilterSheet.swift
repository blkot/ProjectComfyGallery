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
                        .foregroundStyle(kind == nil ? Color.accentColor : Color.primary)
                    Button("Images") { kind = .image }
                        .foregroundStyle(kind == .image ? Color.accentColor : Color.primary)
                    Button("Videos") { kind = .video }
                        .foregroundStyle(kind == .video ? Color.accentColor : Color.primary)
                }

                Section("Evaluation Status") {
                    Button("All") { evaluationState = nil }
                        .foregroundStyle(evaluationState == nil ? Color.accentColor : Color.primary)
                    Button("Not Started") { evaluationState = .notStarted }
                        .foregroundStyle(evaluationState == .notStarted ? Color.accentColor : Color.primary)
                    Button("In Progress") { evaluationState = .inProgress }
                        .foregroundStyle(evaluationState == .inProgress ? Color.accentColor : Color.primary)
                    Button("Complete") { evaluationState = .complete }
                        .foregroundStyle(evaluationState == .complete ? Color.accentColor : Color.primary)
                }

                Section("Trash") {
                    ForEach(LibraryFeature.FilterTrashOption.allCases, id: \.self) { option in
                        Button(option.label) { trash = option }
                            .foregroundStyle(trash == option ? Color.accentColor : Color.primary)
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
