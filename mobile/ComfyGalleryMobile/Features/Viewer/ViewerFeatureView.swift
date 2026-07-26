import SwiftUI
import OSLog

struct ViewerFeatureView: View {
    let initialItem: MobileMediaSummary
    @Bindable var library: LibraryFeature

    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    @State private var currentItemID: String?
    @State private var showControls = true
    @State private var prefetchedIDs: Set<String> = []
    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "Viewer")

    init(initialItem: MobileMediaSummary, library: LibraryFeature) {
        self.initialItem = initialItem
        self.library = library
        _currentItemID = State(initialValue: initialItem.id)
    }

    private var items: [MobileMediaSummary] { library.items }
    private var totalCount: Int { library.total }

    private var currentIndex: Int {
        guard let id = currentItemID,
              let index = items.firstIndex(where: { $0.id == id }) else { return 0 }
        return index
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 0) {
                    ForEach(items) { item in
                        ViewerPageView(item: item)
                            .frame(width: UIScreen.main.bounds.width)
                            .tag(item.id)
                    }
                }
                .scrollTargetLayout()
            }
            .scrollTargetBehavior(.paging)
            .scrollPosition(id: $currentItemID)
            .ignoresSafeArea()
        }
        .overlay(alignment: .top) { topBar }
        .simultaneousGesture(dismissSwipeGesture)
        .onTapGesture {
            withAnimation(.easeInOut(duration: 0.2)) {
                showControls.toggle()
            }
        }
        .onAppear {
            logger.log("Viewer appeared, items.count=\(items.count), total=\(totalCount)")
            Task { await prefetchNeighbors() }
        }
        .onChange(of: currentItemID) { _, _ in
            library.loadMoreIfNearEnd(index: currentIndex)
            Task { await prefetchNeighbors() }
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

                    Text("\(currentIndex + 1) of \(max(totalCount, items.count))")
                        .foregroundStyle(.white)
                        .font(.subheadline)
                }
                .padding()
                .background(.black.opacity(0.5))
            }
        }
    }

    private var dismissSwipeGesture: some Gesture {
        DragGesture(minimumDistance: 50)
            .onEnded { value in
                let horizontal = abs(value.translation.width)
                let vertical = abs(value.translation.height)
                if vertical > horizontal && value.translation.height > 100 {
                    dismiss()
                }
            }
    }

    private func prefetchNeighbors() async {
        let index = currentIndex
        let idsToPrefetch: [String] = [index - 1, index + 1]
            .filter { $0 >= 0 && $0 < items.count }
            .map { items[$0].id }
            .filter { !prefetchedIDs.contains($0) }

        for id in idsToPrefetch {
            prefetchedIDs.insert(id)
        }

        let repo = environment.mediaRepository
        let screenWidth = UIScreen.main.bounds.width
        let screenHeight = UIScreen.main.bounds.height
        let target = CGSize(width: screenWidth, height: screenHeight)

        await withTaskGroup(of: Void.self) { group in
            for id in idsToPrefetch {
                group.addTask {
                    _ = try? await repo.fetchPreviewImage(mediaID: id, targetSize: target)
                }
            }
        }
    }
}

private struct ViewerPageView: View {
    let item: MobileMediaSummary
    @Environment(AppEnvironment.self) private var environment

    @State private var image: UIImage?
    @State private var videoURL: URL?
    @State private var posterImage: UIImage?
    @State private var isLoading = false
    @State private var loadFailed = false
    @State private var loadError: String?
    @State private var scale: CGFloat = 1.0

    private let logger = Logger(subsystem: "com.comfygallery.mobile", category: "ViewerPage")

    var body: some View {
        ZStack {
            Color.black
            content
        }
        .task { await load() }
    }

    @ViewBuilder
    private var content: some View {
        if isLoading && image == nil && videoURL == nil {
            loadingView
        } else if loadFailed {
            errorView(message: loadError ?? "Could not load media")
        } else if item.kind == .video, let url = videoURL {
            VideoPlayerView(videoURL: url, posterImage: posterImage)
        } else if let image = image {
            ImageViewer(image: image, scale: $scale)
        } else if posterImage != nil {
            Color.black
        } else {
            errorView(message: loadError ?? "Media could not be decoded.")
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
                Task { await load() }
            }
            .buttonStyle(.bordered)
            .tint(.white)
        }
    }

    private func load() async {
        isLoading = true
        loadFailed = false
        loadError = nil
        do {
            let repo = environment.mediaRepository
            let target = CGSize(width: UIScreen.main.bounds.width, height: UIScreen.main.bounds.height)
            let img = try await repo.fetchPreviewImage(mediaID: item.id, targetSize: target)
            posterImage = img
            if item.kind == .image {
                image = img
            } else if item.kind == .video {
                videoURL = try await repo.fetchPlaybackVideo(mediaID: item.id)
            }
            isLoading = false
            logger.log("Loaded page id=\(item.id, privacy: .public)")
        } catch let error as APIError {
            isLoading = false
            loadFailed = true
            loadError = error.errorDescription
            logger.error("Failed page id=\(item.id, privacy: .public): \(error.localizedDescription, privacy: .public)")
        } catch {
            isLoading = false
            loadFailed = true
            loadError = error.localizedDescription
            logger.error("Failed page id=\(item.id, privacy: .public): \(error.localizedDescription, privacy: .public)")
        }
    }
}
