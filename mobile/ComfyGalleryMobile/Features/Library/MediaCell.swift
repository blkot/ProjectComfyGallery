import SwiftUI

struct MediaCell: View {
    let item: MobileMediaSummary
    var isSelecting = false
    var isSelected = false
    var showsBadges = true
    var showsClassifierBadge = false
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.displayScale) private var displayScale
    @State private var image: UIImage?
    @State private var failed = false

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Rectangle().fill(.quaternary)
                if let image {
                    Image(uiImage: image).resizable().scaledToFill()
                        .frame(width: geometry.size.width, height: geometry.size.height).clipped()
                } else {
                    Image(systemName: failed ? "exclamationmark.arrow.triangle.2.circlepath" : "photo")
                        .foregroundStyle(.secondary)
                }
                if showsBadges {
                    LinearGradient(colors: [.clear, .black.opacity(0.45)], startPoint: .center, endPoint: .bottom)
                }
                VStack {
                    HStack {
                        if showsBadges, item.isTrash == true { Image(systemName: "trash.fill") }
                        Spacer()
                        if showsClassifierBadge, item.kind == .image {
                            classifierBadge
                        }
                        if isSelecting {
                            Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                                .font(.title3).foregroundStyle(isSelected ? Color.accentColor : .white)
                                .background(Circle().fill(isSelected ? .white : .black.opacity(0.2)))
                        }
                    }
                    Spacer(minLength: 0)
                    HStack(alignment: .bottom) {
                        if showsBadges, item.favorite == true { Image(systemName: "heart.fill") }
                        Spacer(minLength: 0)
                        if showsBadges, item.kind == .video {
                            Image(systemName: "play.fill")
                            if let duration = item.durationLabel { Text(duration).monospacedDigit() }
                        }
                    }
                    .font(.caption2).fontWeight(.semibold)
                }
                .foregroundStyle(.white).padding(7)
                if isSelected { Rectangle().strokeBorder(.tint, lineWidth: 3) }
            }
            .task(id: item.id) {
                do {
                    image = try await environment.mediaRepository.fetchPreviewImage(
                        mediaID: item.id, targetSize: geometry.size, scale: displayScale
                    )
                    failed = false
                } catch { if !Task.isCancelled { failed = true } }
            }
        }
        .aspectRatio(LibraryLayout.tileAspectRatio, contentMode: .fit)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(item.kind == .video ? "视频，\(item.durationLabel ?? "时长未知")" : "照片")
        .accessibilityValue([item.favorite == true ? "已收藏" : nil, item.isTrash == true ? "在废纸篓" : nil,
                             showsClassifierBadge ? classifierAccessibilityValue : nil,
                             isSelected ? "已选择" : nil, failed ? "缩略图加载失败，打开可重试" : nil].compactMap { $0 }.joined(separator: "，"))
    }

    @ViewBuilder private var classifierBadge: some View {
        let status = ClassifierProjection.status(assessment: item.mediaSafetyAssessment, review: item.mediaSafetyReview)
        let rating = ClassifierProjection.effectiveRating(assessment: item.mediaSafetyAssessment, review: item.mediaSafetyReview)
        if status == .processing || status == .failed || status == .unclassified || rating == nil {
            Label(status.title, systemImage: status.symbol)
                .lineLimit(1).font(.caption2).padding(.horizontal, 6).padding(.vertical, 4)
                .background(.black.opacity(0.66), in: Capsule())
        } else if let rating {
            Label("\(rating.title) · \(item.mediaSafetyReview == nil ? "AI" : "人工")", systemImage: rating.symbol)
                .lineLimit(1).font(.caption2).padding(.horizontal, 6).padding(.vertical, 4)
                .background(.black.opacity(0.66), in: Capsule())
        }
    }

    private var classifierAccessibilityValue: String {
        let status = ClassifierProjection.status(assessment: item.mediaSafetyAssessment, review: item.mediaSafetyReview)
        guard let rating = ClassifierProjection.effectiveRating(assessment: item.mediaSafetyAssessment, review: item.mediaSafetyReview) else { return status.title }
        return "Classifier：\(rating.title)，\(item.mediaSafetyReview == nil ? "AI 建议" : "人工确认")"
    }
}
