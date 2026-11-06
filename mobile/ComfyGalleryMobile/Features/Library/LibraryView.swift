import SwiftUI

struct LibraryView: View {
    let tab: AppEnvironment.Tab
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var feature: LibraryFeature
    @State private var showingDrawer = false
    @GestureState private var drawerTranslation: CGFloat = 0
    @State private var showingSettings = false
    @State private var confirmingTrash = false
    @State private var selectedItem: MobileMediaSummary?
    @State private var restoreSequence = 0
    @State private var lastSeenRevision = -1

    init(apiClient: APIClient, tab: AppEnvironment.Tab = .library) {
        self.tab = tab
        _feature = State(initialValue: LibraryFeature(service: LiveGalleryService(apiClient: apiClient)))
    }

    private var searchIsEmpty: Bool { tab == .search && feature.scope.query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    private var refreshKey: RefreshKey { RefreshKey(scope: feature.scope, active: environment.selectedTab == tab, revision: environment.galleryRevision) }

    var body: some View {
        NavigationStack {
            searchableContent
                .navigationTitle(feature.isSelecting ? "已选 \(feature.selectedIDs.count) 项" : (feature.scope.trash == .only ? "废纸篓" : (tab == .search ? "搜索" : "图库")))
                .toolbar { toolbar }
                .safeAreaInset(edge: .bottom, spacing: 0) { if feature.isSelecting { selectionBar } }
                .sheet(isPresented: $showingSettings) { SettingsView(connectionService: environment.connectionService, mediaRepository: environment.mediaRepository) }
                .fullScreenCover(item: $selectedItem, onDismiss: viewerDismissed) { ViewerFeatureView(initialItem: $0, library: feature) }
                .confirmationDialog("将所选 \(feature.selectedIDs.count) 项移入废纸篓？", isPresented: $confirmingTrash, titleVisibility: .visible) {
                    Button("移入废纸篓", role: .destructive) { mutate(trash: true) }
                } message: { Text("内容可在右上角更多菜单的废纸篓中恢复，不会永久删除文件。") }
                .task(id: refreshKey) { await refreshIfNeeded() }
                .accessibilityHidden(showingDrawer)
        }
        .overlay {
            GeometryReader { geometry in
                let width = min(380, geometry.size.width * 0.88)
                if showingDrawer || drawerTranslation > 0 {
                    ZStack(alignment: .leading) {
                        Button(action: closeDrawer) { Color.clear }.buttonStyle(.plain).accessibilityLabel("关闭侧栏")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .background(.black.opacity(showingDrawer ? 0.35 : min(0.35, drawerTranslation / width * 0.35)))
                            .ignoresSafeArea()
                        LibraryFilterDrawer(scope: $feature.scope, apiClient: environment.apiClient, close: closeDrawer)
                            .frame(width: width).frame(maxHeight: .infinity)
                            .offset(x: showingDrawer ? 0 : min(0, drawerTranslation - width))
                    }
                }
            }
        }
        .animation(reduceMotion ? nil : .snappy(duration: 0.25), value: showingDrawer)
        .toolbar(showingDrawer ? .hidden : .visible, for: .tabBar)
    }

    @ViewBuilder private var searchableContent: some View {
        if tab == .search { content.searchable(text: $feature.scope.query, placement: .navigationBarDrawer(displayMode: .always), prompt: "搜索提示词、模型或 LoRA") }
        else { content }
    }

    private var content: some View {
        GeometryReader { geometry in
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: 14) {
                        if let message = feature.notice {
                            HStack { Text(message).font(.footnote); Spacer(); Button("关闭提示", systemImage: "xmark.circle") { feature.notice = nil }.labelStyle(.iconOnly).frame(width: 44, height: 44) }.padding(.horizontal)
                        }
                        if searchIsEmpty {
                            ContentUnavailableView("搜索你的作品", systemImage: "magnifyingglass", description: Text("输入关键词；从左边缘划出侧栏组合筛选。"))
                        } else if feature.items.isEmpty && (feature.isLoading || (feature.loadedScope == nil && feature.errorMessage == nil)) {
                            ProgressView("正在载入图库…").frame(maxWidth: .infinity, minHeight: 260)
                        } else if let error = feature.errorMessage, feature.items.isEmpty {
                            ContentUnavailableView {
                                Label("暂时无法载入", systemImage: "wifi.exclamationmark")
                            } description: { Text(error) } actions: { Button("重试") { Task { await feature.reload() } }.buttonStyle(.borderedProminent) }
                        } else if feature.items.isEmpty {
                            ContentUnavailableView("没有匹配的内容", systemImage: "photo.on.rectangle", description: Text("打开左侧栏调整筛选，或下拉刷新。"))
                        } else {
                            if let error = feature.errorMessage { Text("刷新失败，仍显示上次内容：\(error)").font(.footnote).foregroundStyle(.secondary).padding(.horizontal) }
                            MediaLibraryGrid(feature: feature, width: geometry.size.width) { selectedItem = $0 }
                            paginationFooter
                        }
                    }.padding(.bottom, 16)
                }
                .refreshable { if !searchIsEmpty { await feature.reload(preservingPosition: true) } }
                .simultaneousGesture(edgeGesture)
                .onChange(of: restoreSequence) { if let id = feature.returnAnchorID { proxy.scrollTo(id, anchor: .center) } }
            }
        }.background(.background)
    }

    private var edgeGesture: some Gesture {
        DragGesture(minimumDistance: 15)
            .updating($drawerTranslation) { value, state, _ in
                guard !showingDrawer, !feature.isMutating, value.startLocation.x < 24,
                      value.translation.width > abs(value.translation.height) else { return }
                state = max(0, value.translation.width)
            }
            .onEnded { value in
                guard !showingDrawer, !feature.isMutating, value.startLocation.x < 24,
                      value.translation.width > abs(value.translation.height),
                      value.translation.width > 70 || value.predictedEndTranslation.width > 130 else { return }
                showingDrawer = true
            }
    }

    @ViewBuilder private var paginationFooter: some View {
        if feature.isLoadingMore { ProgressView("正在载入更多…") }
        else if let error = feature.paginationError {
            VStack { Text(error).font(.footnote); Button("重试加载更多") { Task { await feature.loadMore() } } }.padding()
        } else if feature.canLoadMore { Button("载入更多") { Task { await feature.loadMore() } } }
        else { Text("共 \(feature.total) 项").font(.footnote).foregroundStyle(.secondary) }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            Button("打开侧栏", systemImage: "sidebar.left") { showingDrawer = true }.labelStyle(.iconOnly).disabled(feature.isMutating)
        }
        ToolbarItemGroup(placement: .topBarTrailing) {
            if feature.isSelecting {
                Button("选取已加载") { feature.selectLoadedItems() }.disabled(feature.isMutating)
                Button("完成") { feature.endSelection() }.disabled(feature.isMutating)
            } else {
                Button("选择") { feature.isSelecting = true }.disabled(feature.items.isEmpty || searchIsEmpty)
                Menu("更多", systemImage: "ellipsis.circle") {
                    Button("设置", systemImage: "gearshape") { showingSettings = true }
                    Button(feature.scope.trash == .only ? "返回图库" : "废纸篓", systemImage: feature.scope.trash == .only ? "photo.on.rectangle" : "trash") {
                        feature.scope.trash = feature.scope.trash == .only ? .hidden : .only
                    }
                }.labelStyle(.iconOnly)
            }
        }
    }

    private var selectionBar: some View {
        HStack {
            Button(feature.allSelectedAreFavorites ? "取消收藏" : "收藏", systemImage: feature.allSelectedAreFavorites ? "heart.slash" : "heart") { mutate(favorite: !feature.allSelectedAreFavorites) }
            Spacer()
            if feature.isMutating { ProgressView() }
            if feature.scope.trash == .only { Button("恢复", systemImage: "arrow.uturn.backward") { mutate(trash: false) } }
            else { Button("废纸篓", systemImage: "trash", role: .destructive) { confirmingTrash = true } }
        }.font(.subheadline).padding().frame(minHeight: 60).background(.regularMaterial)
            .disabled(feature.selectedIDs.isEmpty || feature.isMutating)
    }

    private func closeDrawer() { showingDrawer = false }
    private func refreshIfNeeded() async {
        guard environment.selectedTab == tab, !searchIsEmpty, selectedItem == nil else { return }
        if tab == .search, feature.loadedScope?.query != feature.scope.query {
            do { try await Task.sleep(for: .milliseconds(300)) } catch { return }
        }
        guard feature.loadedScope != feature.scope || lastSeenRevision != environment.galleryRevision else { return }
        let revision = environment.galleryRevision
        await feature.reload(preservingPosition: feature.loadedScope == feature.scope)
        if !Task.isCancelled, feature.errorMessage == nil { lastSeenRevision = revision }
    }
    private func mutate(favorite: Bool? = nil, trash: Bool? = nil) {
        Task { _ = await feature.mutateSelection(favorite: favorite, trash: trash); environment.galleryRevision += 1; lastSeenRevision = environment.galleryRevision }
    }
    private func viewerDismissed() {
        Task {
            if feature.needsRefresh { await feature.reload(preservingPosition: true); if feature.errorMessage == nil { lastSeenRevision = environment.galleryRevision } }
            restoreSequence += 1
        }
    }
    private struct RefreshKey: Equatable { let scope: GalleryScope; let active: Bool; let revision: Int }
}
