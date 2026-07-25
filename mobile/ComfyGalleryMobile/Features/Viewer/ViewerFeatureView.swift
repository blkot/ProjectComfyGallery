import SwiftUI

struct ViewerFeatureView: View {
    let initialItem: MobileMediaSummary
    let items: [MobileMediaSummary]

    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    @State private var currentIndex: Int
    @State private var image: UIImage?
    @State private var videoURL: URL?
    @State private var posterImage: UIImage?
    @State private var isLoading = true
    @State private var showControls = true

    init(initialItem: MobileMediaSummary, items: [MobileMediaSummary]) {
        self.initialItem = initialItem
        self.items = items
        _currentIndex = State(initialValue: items.firstIndex(where: { $0.id == initialItem.id }) ?? 0)
    }

    private var currentItem: MobileMediaSummary? {
        guard currentIndex >= 0, currentIndex < items.count else { return nil }
        return items[currentIndex]
    }

    var body: some View {
        NavigationStack {
            GeometryReader { geometry in
                ZStack {
                    Color.black.ignoresSafeArea()

                    if let item = currentItem {
                        if isLoading {
                            ProgressView()
                                .tint(.white)
                        } else if item.kind == .video, let url = videoURL {
                            VideoPlayerView(videoURL: url, posterImage: posterImage)
                        } else if let image = image {
                            ImageViewer(image: image)
                        }
                    }
                }
                .overlay(alignment: .top) {
                    if showControls {
                        HStack {
                            Button {
                                dismiss()
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(.white)
                            }

                            Spacer()

                            Text("\(currentIndex + 1) / \(items.count)")
                                .foregroundStyle(.white)
                                .font(.subheadline)
                        }
                        .padding()
                        .background(.black.opacity(0.4))
                    }
                }
                .overlay(alignment: .bottom) {
                    if showControls {
                        HStack {
                            Button {
                                navigateToPrevious()
                            } label: {
                                Image(systemName: "arrow.left.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(currentIndex > 0 ? .white : .gray)
                            }
                            .disabled(currentIndex <= 0)

                            Spacer()

                            Button {
                                navigateToNext()
                            } label: {
                                Image(systemName: "arrow.right.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(currentIndex < items.count - 1 ? .white : .gray)
                            }
                            .disabled(currentIndex >= items.count - 1)
                        }
                        .padding()
                        .background(.black.opacity(0.4))
                    }
                }
                .onTapGesture {
                    withAnimation {
                        showControls.toggle()
                    }
                }
            }
            .navigationBarHidden(true)
        }
        .task {
            await loadCurrentItem()
        }
        .onChange(of: currentIndex) { _, _ in
            Task { await loadCurrentItem() }
        }
    }

    private func loadCurrentItem() async {
        guard let item = currentItem else { return }
        isLoading = true
        image = nil
        videoURL = nil
        posterImage = nil

        do {
            let repo = environment.mediaRepository
            let targetSize = CGSize(width: UIScreen.main.bounds.width, height: UIScreen.main.bounds.width * 1.5)
            posterImage = try await repo.fetchPreviewImage(
                mediaID: item.id,
                targetSize: targetSize
            )
            if item.kind == .image {
                image = posterImage
            } else if item.kind == .video {
                videoURL = try await repo.fetchPlaybackVideo(mediaID: item.id)
            }
        } catch {
            // Loading failed, stay on placeholder
        }
        isLoading = false
    }

    private func navigateToPrevious() {
        guard currentIndex > 0 else { return }
        currentIndex -= 1
    }

    private func navigateToNext() {
        guard currentIndex < items.count - 1 else { return }
        currentIndex += 1
    }
}
