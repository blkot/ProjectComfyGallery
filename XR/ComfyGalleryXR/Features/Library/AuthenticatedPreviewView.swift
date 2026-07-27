import SwiftUI

struct AuthenticatedPreviewView: View {
    @Environment(AppModel.self) private var model
    let media: XRMediaSummary

    @State private var image: UIImage?
    @State private var failed = false
    @Environment(\.displayScale) private var displayScale

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                Rectangle()
                    .fill(.thinMaterial)
                if let image {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                } else if failed {
                    Image(systemName: media.kind == .video ? "video.slash" : "photo.badge.exclamationmark")
                        .font(.title)
                        .foregroundStyle(.secondary)
                        .accessibilityLabel("Preview unavailable")
                } else {
                    ProgressView()
                        .controlSize(.small)
                        .accessibilityLabel("Loading preview")
                }
            }
            .task(id: media.id) {
                failed = false
                do {
                    image = try await model.preview(
                        for: media,
                        pixelSize: CGSize(
                            width: max(480, proxy.size.width * displayScale),
                            height: max(720, proxy.size.height * displayScale)
                        )
                    )
                } catch is CancellationError {
                    return
                } catch {
                    failed = true
                }
            }
        }
        .clipped()
    }
}
