import SwiftUI

struct NewSessionSheet: View {
    @Bindable var feature: ReviewHomeFeature
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Picker("Source", selection: $feature.sourceKind) {
                        Text("Random Unevaluated").tag(SourceKind.random)
                        Text("In Progress").tag(SourceKind.inProgress)
                        Text("Current Library View").tag(SourceKind.filter)
                    }

                    if feature.sourceKind == .filter {
                        Picker("Media Type", selection: Binding(
                            get: { feature.filterKind },
                            set: { feature.filterKind = $0 }
                        )) {
                            Text("All").tag(nil as MediaKind?)
                            Text("Images").tag(MediaKind.image as MediaKind?)
                            Text("Videos").tag(MediaKind.video as MediaKind?)
                        }
                    }
                }

                Section("Settings") {
                    Stepper("Max Items: \(feature.randomLimit)", value: $feature.randomLimit, in: 1...2000, step: 10)

                    Picker("Ordering", selection: $feature.orderingMode) {
                        Text("Random").tag(OrderingMode.random)
                        Text("Stable").tag(OrderingMode.stable)
                    }

                    Toggle("Character Rubric", isOn: $feature.includeCharacter)
                }
            }
            .navigationTitle("New Review")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Start Review") {
                        Task {
                            _ = await feature.createSession()
                            dismiss()
                        }
                    }
                }
            }
        }
    }
}
