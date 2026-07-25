import SwiftUI

struct ReviewWorkspaceView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @State var feature: ReviewWorkspaceFeature

    var body: some View {
        VStack(spacing: 0) {
            // Fixed header
            HStack {
                Button("Stop") {
                    Task { await feature.stop() }
                    dismiss()
                }
                Spacer()
                if let item = feature.reviewItem {
                    Text("\(item.position + 1) / \(item.session.candidateCount)")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                Spacer()
                SaveStateIndicator(state: feature.saveState)
            }
            .padding(.horizontal).padding(.vertical, 8).background(.bar)

            if feature.isLoading {
                Spacer()
                ProgressView("Loading...")
                Spacer()
            } else if let error = feature.errorMessage {
                Spacer()
                VStack(spacing: 12) {
                    Text(error).foregroundStyle(.secondary)
                    Button("Retry") { Task { await feature.load() } }
                }
                Spacer()
            } else if let item = feature.reviewItem {
                // Media stage
                mediaStage(media: item.media)
                    .frame(maxHeight: UIScreen.main.bounds.height * 0.48)

                Divider()

                // Scrollable criteria
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        PromptSection(prompts: item.prompts)

                        ForEach(item.evaluations) { evaluation in
                            VStack(alignment: .leading, spacing: 12) {
                                Text(evaluation.evaluationKind == "character" ? "Character" : "Core Evaluation")
                                    .font(.title3).fontWeight(.semibold)

                                ForEach(evaluation.criteria) { criterion in
                                    CriterionCard(
                                        criterion: criterion,
                                        score: evaluation.scores.first { $0.criterionVersionId == criterion.id },
                                        evaluation: evaluation,
                                        onScore: { value in
                                            Task { await feature.setScore(value, for: criterion, evaluation: evaluation) }
                                        },
                                        onClear: {
                                            Task { await feature.clearScore(for: criterion, evaluation: evaluation) }
                                        },
                                        onNA: {
                                            Task { await feature.setNA(for: criterion, evaluation: evaluation) }
                                        },
                                        isDisabled: feature.saveState == .saving
                                    )
                                }

                                Button {
                                    Task { await feature.toggleTrash(evaluation: evaluation) }
                                } label: {
                                    Label(
                                        evaluation.isTrash ? "Restore from Trash" : "Mark as Trash",
                                        systemImage: evaluation.isTrash ? "arrow.uturn.backward" : "trash"
                                    ).frame(maxWidth: .infinity)
                                }
                                .buttonStyle(.bordered)
                                .tint(evaluation.isTrash ? .green : .red)
                                .padding(.top, 8)
                            }
                        }
                    }
                    .padding()
                }
            }

            // Fixed bottom navigation
            Divider()
            HStack {
                Button { Task { await feature.navigateToPrevious() } } label: {
                    Label("Previous", systemImage: "arrow.left")
                }.disabled(feature.position <= 0)

                Spacer()

                Button { Task { await feature.undoLastAction() } } label: {
                    Label("Undo", systemImage: "arrow.uturn.backward")
                }

                Spacer()

                if feature.isLastItem {
                    Button("Finish Session") {
                        Task { await feature.finishSession() }
                        dismiss()
                    }.buttonStyle(.borderedProminent)
                } else {
                    Button { Task { await feature.navigateToNext() } } label: {
                        Label("Next", systemImage: "arrow.right")
                    }
                }
            }
            .padding(.horizontal).padding(.vertical, 8).background(.bar)
        }
        .sheet(isPresented: $feature.showConflict) {
            ConflictSheet(
                message: feature.conflictMessage,
                serverValue: feature.conflictServerValue,
                localValue: feature.conflictLocalValue,
                onResolve: { useServer in
                    Task { await feature.resolveConflict(useServerValue: useServer) }
                }
            )
        }
        .task { await feature.load() }
    }

    @ViewBuilder
    private func mediaStage(media: ReviewMedia) -> some View {
        Rectangle()
            .fill(Color(.systemGray6))
            .overlay {
                Image(systemName: media.kind == .video ? "play.rectangle" : "photo")
                    .font(.system(size: 48))
                    .foregroundStyle(.secondary)
            }
            .accessibilityLabel(media.kind == .video ? "Video under review" : "Image under review")
    }
}
