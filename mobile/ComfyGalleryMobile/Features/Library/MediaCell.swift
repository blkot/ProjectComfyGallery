import SwiftUI

struct MediaCell: View {
    let item: MobileMediaSummary
    @Environment(AppEnvironment.self) private var environment

    @State private var image: UIImage?
    @State private var loadFailed = false

    private let targetSize = CGSize(width: 200, height: 300)

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                if let image = image {
                    Image(uiImage: image)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: geometry.size.width, height: geometry.size.height)
                        .clipped()
                } else if loadFailed {
                    Color(.systemGray6)
                        .overlay {
                            Image(systemName: item.kind == .video ? "play.slash" : "photo")
                                .foregroundStyle(.secondary)
                        }
                } else {
                    Color(.systemGray6)
                        .overlay {
                            ProgressView()
                        }
                }

                VStack {
                    HStack {
                        Spacer()
                        if item.kind == .video {
                            Image(systemName: "play.rectangle.fill")
                                .font(.caption)
                                .foregroundStyle(.white)
                                .padding(6)
                                .background(.black.opacity(0.5))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                                .padding(4)
                        }
                    }
                    Spacer()
                    HStack {
                        if item.isTrash == true {
                            Image(systemName: "trash.fill")
                                .font(.caption)
                                .foregroundStyle(.red)
                                .padding(4)
                        }
                        Spacer()
                        if let state = item.evaluationState {
                            evaluationIndicator(state)
                                .padding(4)
                        }
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .aspectRatio(2.0 / 3.0, contentMode: .fit)
        .task {
            guard image == nil, !loadFailed else { return }
            do {
                image = try await environment.mediaRepository.fetchPreviewImage(
                    mediaID: item.id,
                    targetSize: targetSize
                )
            } catch {
                loadFailed = true
            }
        }
    }

    @ViewBuilder
    private func evaluationIndicator(_ state: EvaluationState) -> some View {
        switch state {
        case .complete:
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .inProgress:
            Image(systemName: "circle.dotted")
                .foregroundStyle(.orange)
        case .notStarted:
            Image(systemName: "circle")
                .foregroundStyle(.secondary)
        }
    }
}
