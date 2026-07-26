import SwiftUI

struct ReviewWorkspaceView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @State var feature: ReviewWorkspaceFeature

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
                    .frame(maxHeight: UIScreen.main.bounds.height * 0.48)

                Divider()

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
                                        score: feature.score(for: criterion),
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
                Text("\(item.position + 1) / \(item.session.candidateCount)")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer()
            SaveStateIndicator(state: feature.saveState)
        }
        .padding(.horizontal).padding(.vertical, 8).background(.bar)
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
