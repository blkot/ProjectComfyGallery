import SwiftUI

struct MediaActionBar: View {
    let item: MobileMediaSummary
    let disabled: Bool
    let saving: Bool
    let favorite: () -> Void
    let rate: (String) -> Void
    let save: () -> Void
    let trash: () -> Void

    var body: some View {
        HStack(spacing: 16) {
            Button(item.favorite == true ? "取消收藏" : "收藏", systemImage: item.favorite == true ? "heart.fill" : "heart", action: favorite)
                .labelStyle(.iconOnly).tint(item.favorite == true ? .pink : .primary).frame(minWidth: 44, minHeight: 44)
            Spacer(minLength: 0)
            HStack(spacing: 0) {
                rating("sfw", label: "N", name: "普通内容 SFW")
                rating("nsfw", label: "R", name: "限制内容 NSFW")
            }.background(.quaternary, in: .capsule)
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

    private func rating(_ value: String, label: String, name: String) -> some View {
        Button { rate(value) } label: {
            Text(label).font(.headline).frame(minWidth: 44, minHeight: 44)
                .background(item.contentRating == value ? Color.accentColor : .clear, in: .capsule)
        }
        .accessibilityLabel(name).accessibilityValue(item.contentRating == value ? "已选择" : "未选择")
        .disabled(item.contentRating == value)
    }
}
