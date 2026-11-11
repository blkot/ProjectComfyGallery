import SwiftUI

struct LibraryFilterDrawer: View {
    @Binding var scope: GalleryScope
    let apiClient: APIClient
    let close: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("图库筛选").font(.title2).bold()
                Spacer()
                Button("关闭筛选", systemImage: "xmark", action: close).labelStyle(.iconOnly).frame(width: 44, height: 44)
            }.padding(.horizontal, 20).padding(.top, 12)
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Media Type").font(.headline)
                        HStack {
                            choice("全部", icon: "square.grid.2x2", selected: scope.kind == nil) { scope.kind = nil }
                            choice("照片", icon: "photo", selected: scope.kind == .image) { scope.kind = .image }
                            choice("视频", icon: "video", selected: scope.kind == .video) { scope.kind = .video }
                        }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Favorite").font(.headline)
                        HStack {
                            choice("全部", icon: "square.grid.2x2", selected: scope.favorite == .all) { scope.favorite = .all }
                            choice("收藏", icon: "heart.fill", selected: scope.favorite == .only) { scope.favorite = .only }
                            choice("未收藏", icon: "heart.slash", selected: scope.favorite == .excluded) { scope.favorite = .excluded }
                        }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Content Safety").font(.headline)
                        HStack {
                            choice("全部", icon: "circle.lefthalf.filled", selected: scope.rating == .all) { scope.rating = .all }
                            choice("SFW", icon: "checkmark.shield", selected: scope.rating == .sfw) { scope.rating = .sfw }
                            choice("NSFW", icon: "exclamationmark.shield", selected: scope.rating == .nsfw) { scope.rating = .nsfw }
                        }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Classifier Status").font(.headline)
                        if scope.kind == .video {
                            Label("Classifier 筛选只适用于照片。", systemImage: "info.circle")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                            choice("全部", icon: "square.grid.2x2", selected: scope.classifierStatus == nil) { scope.classifierStatus = nil }
                            ForEach(ClassifierStatus.allCases, id: \.self) { status in
                                choice(status.title, icon: status.symbol, selected: scope.classifierStatus == status) {
                                    scope.classifierStatus = status
                                }
                            }
                        }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Classifier Rating").font(.headline)
                        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                            choice("全部", icon: "square.grid.2x2", selected: scope.classifierRating == nil) { scope.classifierRating = nil }
                            ForEach(ClassifierRating.allCases, id: \.self) { rating in
                                choice(rating.title, icon: rating.symbol, selected: scope.classifierRating == rating) {
                                    scope.classifierRating = rating
                                }
                            }
                        }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Character LoRA").font(.headline)
                        CharacterLoraList(apiClient: apiClient, selected: $scope.characterLora)
                    }
                }.padding(20)
            }
            Button("重置筛选") {
                scope.kind = nil; scope.favorite = .all; scope.rating = .all; scope.characterLora = nil
                scope.classifierStatus = nil; scope.classifierRating = nil
            }.frame(maxWidth: .infinity, minHeight: 48).padding(.bottom, 8)
        }
        .background(.background)
        .accessibilityAddTraits(.isModal)
        .simultaneousGesture(DragGesture(minimumDistance: 35).onEnded { if $0.translation.width < -70, abs($0.translation.width) > abs($0.translation.height) { close() } })
    }

    private func choice(_ text: String, icon: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 6) { Image(systemName: icon).font(.title3); Text(text).font(.caption) }
                .frame(maxWidth: .infinity, minHeight: 60)
                .foregroundStyle(selected ? Color.white : Color.primary)
                .background(selected ? Color.accentColor : Color.secondary.opacity(0.12), in: .rect(cornerRadius: 12))
        }.accessibilityLabel(text).accessibilityValue(selected ? "已选择" : "未选择")
    }
}
