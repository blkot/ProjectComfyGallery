import SwiftUI

struct NewSessionSheet: View {
    @Bindable var feature: ReviewHomeFeature
    @Environment(\.dismiss) private var dismiss
    let onCreated: (ReviewSession) -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Picker("Source", selection: $feature.sourceKind) {
                        Text("Random Unevaluated").tag(SourceKind.random)
                        Text("In Progress").tag(SourceKind.inProgress)
                        Text("Current Library View").tag(SourceKind.filter)
                    }
                    .onChange(of: feature.sourceKind) { _, newValue in
                        switch newValue {
                        case .random: feature.orderingMode = .random
                        case .inProgress: feature.orderingMode = .stable
                        case .filter: feature.orderingMode = .random
                        }
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

                if let error = feature.errorMessage {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("New Review")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task {
                            if let session = await feature.createSession() {
                                onCreated(session)
                                dismiss()
                            }
                        }
                    } label: {
                        if feature.isCreating {
                            HStack(spacing: 6) {
                                ProgressView().scaleEffect(0.7)
                                Text("Creating…")
                            }
                        } else {
                            Text("Start Review")
                        }
                    }
                    .disabled(feature.isCreating)
                }
            }
        }
    }
}
