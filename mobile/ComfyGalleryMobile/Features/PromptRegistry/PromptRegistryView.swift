import SwiftUI

struct PromptRegistryView: View {
    let initialScope: PromptUsageScope?
    let canDismiss: Bool
    @State private var feature: PromptRegistryFeature
    @State private var choosingCharacter = false
    @State private var selectedItem: MobileMediaSummary?
    @State private var restoreSequence = 0
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    init(apiClient: APIClient, initialScope: PromptUsageScope? = nil, canDismiss: Bool = false) {
        self.initialScope = initialScope
        self.canDismiss = canDismiss
        _feature = State(initialValue: PromptRegistryFeature(apiClient: apiClient))
    }

    var body: some View {
        NavigationStack {
            GeometryReader { geometry in
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 14) {
                            PromptLookupForm(feature: feature) { choosingCharacter = true }
                            if let error = feature.errorMessage ?? feature.library.errorMessage {
                                Text(error).foregroundStyle(.red).font(.footnote).padding(.horizontal)
                                if let scope = feature.activeScope { Button("重试查询") { Task { await feature.open(scope) } }.padding(.horizontal) }
                            }
                            if feature.isLoading { ProgressView("正在加载词库与媒体…").frame(maxWidth: .infinity) }
                            if let lookup = feature.lookup {
                                VStack(alignment: .leading, spacing: 12) {
                                    Text(lookup.promptID).font(.title3).bold().textSelection(.enabled)
                                    if let entry = lookup.entry {
                                        DisclosureGroup("Positive Prompt") { Text(entry.prompt.isEmpty ? "提示词为空" : entry.prompt).textSelection(.enabled) }
                                        if let negative = entry.negativePrompt, !negative.isEmpty { DisclosureGroup("Negative Prompt") { Text(negative).textSelection(.enabled) } }
                                    } else { Text("此 ID 尚未注册定义；仍可浏览已匹配的媒体。").font(.footnote).foregroundStyle(.secondary) }
                                    Text("Media usage · \(feature.library.total) 项").font(.headline)
                                }.padding(.horizontal, 16)
                            }
                            if feature.activeScope != nil {
                                MediaLibraryGrid(feature: feature.library, width: geometry.size.width) { selectedItem = $0 }
                                if feature.library.isLoadingMore { ProgressView().frame(maxWidth: .infinity) }
                                if let error = feature.library.paginationError { Text(error).font(.footnote).padding(.horizontal) }
                                if feature.library.canLoadMore {
                                    Button("载入更多") { Task { await feature.library.loadMore() } }.padding()
                                }
                                if !feature.isLoading && feature.library.items.isEmpty && feature.library.errorMessage == nil {
                                    ContentUnavailableView("没有匹配的 Media usage", systemImage: "photo.on.rectangle", description: Text("试试其他 Character LoRA，或核对 Source 与 Index。"))
                                }
                            } else { ContentUnavailableView("按 Prompt 查找作品", systemImage: "text.book.closed", description: Text("输入完整 Prompt ID，或使用 Source + Index。")) }
                        }.padding(.bottom, 24)
                    }
                    .refreshable { if let scope = feature.activeScope { await feature.open(scope) } }
                    .onChange(of: restoreSequence) { if let id = feature.library.returnAnchorID { proxy.scrollTo(id, anchor: .center) } }
                }
            }
            .navigationTitle("词库")
            .toolbar { if canDismiss { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } } }
            .sheet(isPresented: $choosingCharacter) {
                NavigationStack {
                    ScrollView { CharacterLoraList(apiClient: environment.apiClient, selected: $feature.character).padding() }
                        .navigationTitle("Character LoRA").navigationBarTitleDisplayMode(.inline)
                        .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { choosingCharacter = false } } }
                }.presentationDetents([.medium, .large])
            }
            .fullScreenCover(item: $selectedItem, onDismiss: viewerDismissed) { item in ViewerFeatureView(initialItem: item, library: feature.library) }
            .task { if let initialScope, feature.activeScope == nil { await feature.open(initialScope) } }
            .task(id: feature.character) { await feature.changeCharacter() }
            .task(id: environment.galleryRevision) {
                if selectedItem == nil, feature.activeScope != nil { await feature.library.reload(preservingPosition: true) }
            }
        }
    }

    private func viewerDismissed() {
        Task {
            if feature.library.needsRefresh { await feature.library.reload(preservingPosition: true) }
            restoreSequence += 1
        }
    }
}
