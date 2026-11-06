import SwiftUI

/// Only the active page owns a player or full-resolution image request.
struct ViewerMediaView: View {
    let item: MobileMediaSummary
    let targetSize: CGSize
    var isActive = true
    @Binding var scale: CGFloat
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.displayScale) private var displayScale
    @State private var poster: UIImage?
    @State private var original: UIImage?
    @State private var videoURL: URL?
    @State private var errorMessage: String?
    @State private var retry = 0
    @State private var loading = true

    var body: some View {
        ZStack {
            Color.black
            if let videoURL { VideoPlayerView(videoURL: videoURL, posterImage: poster) }
            else if let image = original ?? poster {
                ImageViewer(image: image, scale: $scale)
            }
            if loading {
                ProgressView(item.kind == .video ? "正在缓存视频…" : "正在加载原图…")
                    .padding().background(.regularMaterial, in: .rect(cornerRadius: 16))
            } else if let errorMessage {
                VStack(spacing: 12) {
                    Text(errorMessage).font(.footnote).multilineTextAlignment(.center)
                    Button("重试加载") { retry += 1 }.buttonStyle(.borderedProminent)
                }.padding().background(.regularMaterial, in: .rect(cornerRadius: 16)).padding(24)
            }
        }
        .task(id: "\(retry)-\(isActive)") {
            if !isActive { original = nil; videoURL = nil }
            loading = true
            errorMessage = nil
            let repository = environment.mediaRepository
            poster = try? await repository.fetchPreviewImage(mediaID: item.id, targetSize: targetSize, scale: displayScale)
            guard !Task.isCancelled else { return }
            guard isActive else { loading = false; return }
            do {
                if item.kind == .image {
                    let image = try await repository.fetchOriginalImage(mediaID: item.id, targetSize: targetSize, scale: displayScale)
                    try Task.checkCancellation()
                    original = image
                } else {
                    let url = try await repository.fetchPlaybackVideo(mediaID: item.id)
                    try Task.checkCancellation()
                    videoURL = url
                }
            } catch {
                if !Task.isCancelled { errorMessage = error.localizedDescription }
            }
            loading = false
        }
    }
}
