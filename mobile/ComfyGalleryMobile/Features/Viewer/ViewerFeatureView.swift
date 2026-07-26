import SwiftUI
import OSLog

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
    @State private var loadErrorText: String?
    @State private var showControls = true
    @State private var currentScale: CGFloat = 1.0

    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "Viewer")

    init(initialItem: MobileMediaSummary, items: [MobileMediaSummary]) {
        self.initialItem = initialItem
        self.items = items
        let initialIndex = items.firstIndex(where: { $0.id == initialItem.id }) ?? 0
        _currentIndex = State(initialValue: initialIndex)
    }

    private var currentItem: MobileMediaSummary? {
        guard currentIndex >= 0, currentIndex < items.count else { return nil }
        return items[currentIndex]
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            content
        }
        .overlay(alignment: .top) { topBar }
        .simultaneousGesture(navigationSwipeGesture)
        .onTapGesture {
            withAnimation(.easeInOut(duration: 0.2)) {
                showControls.toggle()
            }
        }
        .task {
            logger.log("Viewer .task fired, items.count=\(items.count), currentIndex=\(currentIndex)")
            await loadCurrentItem()
        }
        .onChange(of: currentIndex) { _, newValue in
            logger.log("Viewer index changed to \(newValue)")
            image = nil
            videoURL = nil
            posterImage = nil
            isLoading = true
            loadFailed = false
            loadErrorText = nil
            currentScale = 1.0
            Task { await loadCurrentItem() }
        }
    }

    @ViewBuilder
    private var content: some View {
        if let item = currentItem {
            if isLoading {
                loadingView
            } else if loadFailed {
                errorView(message: loadErrorText ?? "Could not load media")
            } else if item.kind == .video, let url = videoURL {
                VideoPlayerView(videoURL: url, posterImage: posterImage)
            } else if let image = image {
                ImageViewer(image: image, scale: $currentScale)
            } else {
                errorView(message: "Media could not be decoded.")
            }
        } else {
            errorView(message: "No item at position \(currentIndex).")
        }
    }

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.4)
                .tint(.white)
            Text("Loading…")
                .font(.footnote)
                .foregroundStyle(.white.opacity(0.7))
        }
    }

    private func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 40))
                .foregroundStyle(.orange)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.8))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Button("Retry") {
                Task { await loadCurrentItem() }
            }
            .buttonStyle(.bordered)
            .tint(.white)
        }
    }

    private var topBar: some View {
        Group {
            if showControls {
                HStack {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.white)
                    }
                    .accessibilityLabel("Close")

                    Spacer()

                    Text("\(currentIndex + 1) of \(items.count)")
                        .foregroundStyle(.white)
                        .font(.subheadline)
                        .accessibilityLabel("Item \(currentIndex + 1) of \(items.count)")
                }
                .padding()
                .background(.black.opacity(0.5))
            }
        }
    }

    private var navigationSwipeGesture: some Gesture {
        DragGesture(minimumDistance: 40)
            .onEnded { value in
                guard currentScale <= 1.0 else { return }
                let horizontal = abs(value.translation.width)
                let vertical = abs(value.translation.height)
                if horizontal > vertical {
                    if value.translation.width < -40 {
                        navigateToNext()
                    } else if value.translation.width > 40 {
                        navigateToPrevious()
                    }
                } else if value.translation.height > 80 {
                    dismiss()
                }
            }
    }

    private func loadCurrentItem() async {
        guard let item = currentItem else {
            logger.error("loadCurrentItem: currentItem is nil (index=\(currentIndex), count=\(items.count))")
            isLoading = false
            loadFailed = true
            loadErrorText = "No item available at this position."
            return
        }
        isLoading = true
        loadFailed = false
        loadErrorText = nil

        do {
            let repo = environment.mediaRepository
            let screenWidth = UIScreen.main.bounds.width
            let screenHeight = UIScreen.main.bounds.height
            let targetSize = CGSize(width: screenWidth, height: screenHeight)
            logger.log("Loading media id=\(item.id, privacy: .public) at \(screenWidth)x\(screenHeight)")
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
            logger.log("Loaded media id=\(item.id, privacy: .public)")
        } catch let error as APIError {
            isLoading = false
            loadFailed = true
            loadErrorText = error.errorDescription
            logger.error("Failed to load media id=\(item.id, privacy: .public): \(error.localizedDescription, privacy: .public)")
        } catch {
            isLoading = false
            loadFailed = true
            loadErrorText = error.localizedDescription
            logger.error("Failed to load media id=\(item.id, privacy: .public): \(error.localizedDescription, privacy: .public)")
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
