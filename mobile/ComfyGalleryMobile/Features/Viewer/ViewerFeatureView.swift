import SwiftUI

struct ViewerFeatureView: View {
    @Bindable var library: LibraryFeature
    @State private var feature: ViewerFeature
    @State private var saver: PhotoLibrarySaver?
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss
    @Environment(\.displayScale) private var displayScale
    @State private var pageID: String?
    @State private var pagerIsInteracting = false
    @State private var scale: CGFloat = 1
    @State private var showingInfo = false
    @State private var confirmingTrash = false
    @State private var pendingPrompt: PromptUsageScope?
    @State private var promptRoute: PromptUsageScope?

    init(initialItem: MobileMediaSummary, library: LibraryFeature) {
        self.library = library
        _feature = State(initialValue: ViewerFeature(item: initialItem, scope: library.scope, service: library.service))
        _pageID = State(initialValue: initialItem.id)
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            GeometryReader { geometry in
                ViewerPager(pages: feature.pages, selection: $pageID, isInteracting: $pagerIsInteracting,
                            isEnabled: scale <= 1.05 && !feature.isWorking && saver?.isSaving != true && !showingInfo && promptRoute == nil,
                            policy: ViewerPagingPolicy(), showDetails: { showingInfo = true }, close: { dismiss() }) { item, size in
                    ViewerMediaView(item: item, targetSize: size,
                                    isActive: pageID == item.id && !showingInfo && promptRoute == nil,
                                    scale: pageID == item.id ? $scale : .constant(1),
                                    onDoubleTap: { toggleFavorite(id: item.id) })
                }
                .task(id: feature.prefetchKey) {
                    await environment.mediaRepository.prepareViewerWindow(currentID: feature.item.id, neighbors: feature.neighbors,
                                                                         targetSize: geometry.size, scale: displayScale)
                }
            }
        }
        .safeAreaInset(edge: .top, spacing: 0) { header }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            MediaActionBar(item: feature.item, disabled: feature.isWorking || !feature.canMutate || pageID != feature.item.id || pagerIsInteracting,
                           saving: saver?.isSaving == true,
                           favorite: { mutate(favorite: feature.item.favorite != true) },
                           rate: { mutate(rating: $0) }, save: save,
                           trash: { if feature.item.isTrash == true { mutate(trash: false) } else { confirmingTrash = true } })
                .overlay(alignment: .top) {
                    ViewerStatusOverlay(message: feature.errorMessage ?? saver?.message,
                                        hasError: feature.errorMessage != nil, permissionDenied: saver?.permissionDenied == true,
                                        retry: { Task { await feature.loadContext() } })
                        .alignmentGuide(.top) { $0[.bottom] + 8 }
                }
        }
        .preferredColorScheme(.dark)
        .interactiveDismissDisabled(feature.isMutating || pagerIsInteracting || saver?.isSaving == true)
        .confirmationDialog("移入废纸篓？", isPresented: $confirmingTrash, titleVisibility: .visible) {
            Button("移入废纸篓", role: .destructive) { mutate(trash: true) }
        } message: { Text("内容仍可恢复，不会永久删除文件。") }
        .sheet(isPresented: $showingInfo, onDismiss: {
            if let route = pendingPrompt { promptRoute = route; pendingPrompt = nil }
        }) {
            MediaInfoSheet(item: feature.item, apiClient: environment.apiClient) { pendingPrompt = $0 }
        }
        .sheet(item: $promptRoute) { route in
            PromptRegistryView(apiClient: environment.apiClient, initialScope: route, canDismiss: true)
        }
        .task(id: pageID) { await activatePage() }
        .task(id: feature.item.id) {
            scale = 1
            saver?.clearMessage()
            await library.rememberViewed(feature.item)
        }
        .onDisappear { Task { await environment.mediaRepository.endViewerPrefetch() } }
    }

    private var header: some View {
        HStack {
            Button("关闭", systemImage: "chevron.down") { dismiss() }.labelStyle(.iconOnly).frame(width: 44, height: 44)
                .disabled(feature.isMutating || pagerIsInteracting || saver?.isSaving == true)
            Spacer()
            VStack(spacing: 2) {
                if let date = feature.item.fileDate { Text(date, format: .dateTime.year().month().day()).font(.headline) }
                else { Text(feature.item.kind == .image ? "照片" : "视频").font(.headline) }
                if feature.outsideScope { Text("已移出当前筛选").font(.caption).foregroundStyle(.secondary) }
                else if let navigation = feature.navigation { Text("\(navigation.position) / \(navigation.total)").font(.caption).foregroundStyle(.secondary) }
            }
            Spacer()
            if feature.isWorking { ProgressView().frame(width: 44, height: 44) }
            else {
                Button("媒体详情 · 向上轻扫", systemImage: "info.circle") { showingInfo = true }
                    .labelStyle(.iconOnly).frame(width: 44, height: 44)
                    .disabled(pagerIsInteracting || saver?.isSaving == true)
            }
        }.padding(.horizontal, 12).background(.regularMaterial)
    }

    private func activatePage() async {
        if saver == nil { saver = PhotoLibrarySaver(apiClient: environment.apiClient) }
        guard let id = pageID else { return }
        if id == feature.item.id { await feature.loadContext() }
        else { await feature.open(id: id) }
        guard !Task.isCancelled else { return }
        if feature.item.id != id { pageID = feature.item.id }
    }

    private func toggleFavorite(id: String) {
        guard id == feature.item.id, pageID == id, feature.item.kind == .image,
              feature.canMutate, !feature.isWorking, !pagerIsInteracting, saver?.isSaving != true else { return }
        mutate(favorite: feature.item.favorite != true)
    }

    private func mutate(favorite: Bool? = nil, trash: Bool? = nil, rating: String? = nil) {
        Task {
            await feature.mutate(favorite: favorite, trash: trash, rating: rating)
            library.update(feature.item)
            environment.galleryRevision += 1
        }
    }

    private func save() {
        let item = feature.item
        Task { await saver?.save(item) }
    }
}
