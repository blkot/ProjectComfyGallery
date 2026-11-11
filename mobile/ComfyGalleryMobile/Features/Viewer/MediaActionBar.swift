import SwiftUI

struct MediaActionBar: View {
    let item: MobileMediaSummary
    let disabled: Bool
    let saving: Bool
    let favorite: () -> Void
    let classifier: () -> Void
    let save: () -> Void
    let trash: () -> Void

    var body: some View {
        HStack(spacing: 16) {
            Button(item.favorite == true ? "取消收藏" : "收藏", systemImage: item.favorite == true ? "heart.fill" : "heart", action: favorite)
                .labelStyle(.iconOnly).tint(item.favorite == true ? .pink : .primary).frame(minWidth: 44, minHeight: 44)
            Spacer(minLength: 0)
            Button(classifierTitle, systemImage: classifierSymbol, action: classifier)
                .labelStyle(.iconOnly).frame(minWidth: 44, minHeight: 44)
            Spacer(minLength: 0)
            Button("保存到系统相册", systemImage: "square.and.arrow.down", action: save)
                .labelStyle(.iconOnly).frame(minWidth: 44, minHeight: 44).disabled(saving)
                .overlay { if saving { ProgressView().padding(10).background(.regularMaterial, in: .circle) } }
            Spacer(minLength: 0)
            Button(item.isTrash == true ? "恢复" : "移入废纸篓", systemImage: item.isTrash == true ? "arrow.uturn.backward" : "trash", action: trash)
                .labelStyle(.iconOnly).frame(minWidth: 44, minHeight: 44)
        }
        .disabled(disabled || saving).padding(.horizontal, 16).padding(.vertical, 8).background(.regularMaterial)
    }

    private var classifierTitle: String {
        guard let rating = ClassifierProjection.effectiveRating(assessment: item.mediaSafetyAssessment, review: item.mediaSafetyReview) else {
            return "打开内容分类"
        }
        return "内容分类：\(rating.title)，\(item.mediaSafetyReview == nil ? "AI 建议" : "人工确认")"
    }

    private var classifierSymbol: String {
        ClassifierProjection.effectiveRating(assessment: item.mediaSafetyAssessment, review: item.mediaSafetyReview)?.symbol ?? "checkmark.shield"
    }
}
