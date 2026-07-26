import SwiftUI

struct ReviewWorkspaceView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @State var feature: ReviewWorkspaceFeature
    @State private var showingSaveError = false

    var body: some View {
        VStack(spacing: 0) {
            header

            if feature.isLoading {
                Spacer()
                ProgressView("Loading...")
                Spacer()
            } else if let error = feature.errorMessage, feature.reviewItem == nil {
                Spacer()
                VStack(spacing: 12) {
                    Text(error).foregroundStyle(.secondary)
                    Button("Retry") { Task { await feature.load() } }
                }
                Spacer()
            } else if let item = feature.reviewItem {
                mediaStage(media: item.media)
                    .frame(maxHeight: UIScreen.main.bounds.height * 0.4)

                Divider()

                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        PromptSection(prompts: item.prompts)
                        ForEach(item.evaluations) { evaluation in
                            evaluationSection(evaluation)
                        }
                    }
                    .padding()
                }
            }

            bottomBar
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
        .alert("Save failed", isPresented: $showingSaveError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(feature.lastSaveError ?? "The last change could not be saved.")
        }
        .onChange(of: feature.requiresReconnect) { _, needsReconnect in
            if needsReconnect {
                environment.isConnected = false
                dismiss()
            }
        }
        .task { await feature.load() }
    }

    private var header: some View {
        HStack {
            Button("Stop") {
                Task {
                    await feature.stop()
                    dismiss()
                }
            }
            Spacer()
            if let item = feature.reviewItem {
                VStack(spacing: 2) {
                    Text("\(item.position + 1) / \(item.session.candidateCount)")
                        .font(.subheadline).foregroundStyle(.secondary)
                    if let state = feature.primaryEvaluationState {
                        evaluationStateBadge(state)
                    }
                }
            }
            Spacer()
            SaveStateIndicator(state: feature.saveState) {
                showingSaveError = true
            }
        }
        .padding(.horizontal).padding(.vertical, 8).background(.bar)
    }

    @ViewBuilder
    private func evaluationSection(_ evaluation: Evaluation) -> some View {
        let completion = feature.criteriaCompletion(forEvaluation: evaluation.id)
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(evaluation.evaluationKind == "character" ? "Character" : "Core Evaluation")
                    .font(.title3).fontWeight(.semibold)
                Spacer()
                evaluationStateBadge(evaluation.progressState)
            }

            if completion.total > 0 {
                Text("\(completion.scored) of \(completion.total) criteria scored")
                    .font(.caption).foregroundStyle(.secondary)
            }

            ForEach(evaluation.criteria) { criterion in
                CriterionCard(
                    criterion: criterion,
                    score: feature.score(forCriterion: criterion.id),
                    onScore: { value in
                        Task { await feature.setScore(value, criterionID: criterion.id) }
                    },
                    onClear: {
                        Task { await feature.clearScore(criterionID: criterion.id) }
                    },
                    onNA: {
                        Task { await feature.setNA(criterionID: criterion.id) }
                    },
                    isDisabled: feature.saveState == .saving
                )
            }

            Button {
                Task { await feature.toggleTrash(evaluationID: evaluation.id) }
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

    private var bottomBar: some View {
        VStack(spacing: 0) {
            Divider()
            HStack {
                Button { Task { await feature.navigateToPrevious() } } label: {
                    Label("Previous", systemImage: "arrow.left")
                }.disabled(feature.position <= 0 || feature.saveState == .saving)

                Spacer()

                Button { Task { await feature.undoLastAction() } } label: {
                    Label("Undo", systemImage: "arrow.uturn.backward")
                }
                .disabled(feature.saveState == .saving)

                Spacer()

                if feature.isLastItem {
                    Button {
                        Task {
                            await feature.finishSession()
                            dismiss()
                        }
                    } label: {
                        Text("Finish Session")
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    Button { Task { await feature.navigateToNext() } } label: {
                        Label("Next", systemImage: "arrow.right")
                    }
                    .disabled(feature.saveState == .saving)
                }
            }
            .padding(.horizontal).padding(.vertical, 8).background(.bar)
        }
    }

    @ViewBuilder
    private func evaluationStateBadge(_ state: ProgressState) -> some View {
        let appearance: (String, Color, String) = {
            switch state {
            case .notStarted: return ("Not started", .secondary, "circle")
            case .inProgress: return ("In progress", .orange, "circle.dotted")
            case .complete: return ("Complete", .green, "checkmark.circle.fill")
            }
        }()
        Label(appearance.0, systemImage: appearance.2)
            .font(.caption2)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(appearance.1.opacity(0.15))
            .foregroundStyle(appearance.1)
            .clipShape(Capsule())
    }

    @ViewBuilder
    private func mediaStage(media: ReviewMedia) -> some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if feature.loadMediaFailed {
                VStack(spacing: 12) {
                    Image(systemName: media.kind == .video ? "play.slash" : "photo")
                        .font(.system(size: 40))
                        .foregroundStyle(.secondary)
                    Text("Could not load media")
                        .foregroundStyle(.secondary)
                    Button("Retry") {
                        Task { await feature.reloadMedia() }
                    }
                    .buttonStyle(.bordered)
                    .tint(.white)
                }
            } else if media.kind == .video, let videoURL = feature.mediaVideoURL {
                VideoPlayerView(videoURL: videoURL, posterImage: feature.mediaPosterImage)
            } else if let image = feature.mediaImage {
                ImageViewer(image: image)
            } else {
                ProgressView()
                    .tint(.white)
                    .scaleEffect(1.2)
            }
        }
        .accessibilityLabel(media.kind == .video ? "Video under review" : "Image under review")
    }
}
