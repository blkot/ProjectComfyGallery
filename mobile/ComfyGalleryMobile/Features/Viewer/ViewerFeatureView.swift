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
    @State private var loadFailed = false
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
        ZStack {
            Color.black.ignoresSafeArea()

                if let item = currentItem {
                    if isLoading {
                        VStack(spacing: 12) {
                            ProgressView()
                                .tint(.white)
                            Text("Loading...")
                                .foregroundStyle(.secondary)
                        }
                    } else if loadFailed {
                        VStack(spacing: 16) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.system(size: 40))
                                .foregroundStyle(.orange)
                            Text("Could not load media")
                                .foregroundStyle(.secondary)
                            Button("Retry") {
                                Task { await loadCurrentItem() }
                            }
                            .buttonStyle(.bordered)
                            .tint(.white)
                        }
                    } else if item.kind == .video, let url = videoURL {
                        VideoPlayerView(videoURL: url, posterImage: posterImage)
                    } else if let image = image {
                        ImageViewer(image: image)
                    } else {
                        VStack(spacing: 16) {
                            Image(systemName: item.kind == .video ? "play.slash" : "photo")
                                .font(.system(size: 40))
                                .foregroundStyle(.secondary)
                            Text("Could not load media")
                                .foregroundStyle(.secondary)
                            Button("Retry") {
                                Task { await loadCurrentItem() }
                            }
                            .buttonStyle(.bordered)
                            .tint(.white)
                        }
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
        .task {
            // Delay load to let presentation animation complete
            try? await Task.sleep(nanoseconds: 400_000_000)
            await loadCurrentItem()
        }
        .onChange(of: currentIndex) { _, _ in
            image = nil
            videoURL = nil
            posterImage = nil
            isLoading = true
            loadFailed = false
            Task {
                try? await Task.sleep(nanoseconds: 200_000_000)
                await loadCurrentItem()
            }
        }
    }

    private func loadCurrentItem() async {
        guard let item = currentItem else { return }
        isLoading = true
        loadFailed = false

        do {
            let repo = environment.mediaRepository
            let targetSize = CGSize(width: UIScreen.main.bounds.width, height: UIScreen.main.bounds.height)
            let img = try await repo.fetchPreviewImage(
                mediaID: item.id,
                targetSize: targetSize
            )
            posterImage = img
            if item.kind == .image {
                image = img
            } else if item.kind == .video {
                videoURL = try await repo.fetchPlaybackVideo(mediaID: item.id)
            }
            isLoading = false
        } catch {
            isLoading = false
            loadFailed = true
        }
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
