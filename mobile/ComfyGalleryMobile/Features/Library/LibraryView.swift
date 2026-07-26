import SwiftUI

struct LibraryView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: LibraryFeature
    @State private var showingFilters = false
    @State private var selectedItem: MobileMediaSummary?
    @State private var showingViewer = false

    init(apiClient: APIClient, mediaRepository: MediaRepository) {
        _feature = State(initialValue: LibraryFeature(apiClient: apiClient, mediaRepository: mediaRepository))
    }

    var body: some View {
        NavigationStack {
            Group {
                if feature.isLoading && feature.items.isEmpty {
                    ProgressView("Loading...")
                } else if let error = feature.errorMessage, feature.items.isEmpty {
                    VStack(spacing: 12) {
                        Text(error)
                            .foregroundStyle(.secondary)
                        Button("Retry") {
                            Task { await feature.load() }
                        }
                        .buttonStyle(.bordered)
                    }
                } else if feature.items.isEmpty {
                    Text("No media matched this view.")
                        .foregroundStyle(.secondary)
                } else {
                    gridView
                }
            }
            .navigationTitle("Library")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingFilters = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                            .symbolVariant(filtersActive ? .fill : .none)
                    }
                }
            }
            .sheet(isPresented: $showingFilters) {
                FilterSheet(
                    kind: $feature.filterKind,
                    evaluationState: $feature.filterEvaluationState,
                    trash: $feature.filterTrash
                )
                .onDisappear {
                    feature.applyFilters()
                }
            }
            .fullScreenCover(item: $selectedItem) { item in
                ViewerFeatureView(initialItem: item, items: feature.items)
            }
        }
        .task {
            if feature.items.isEmpty {
                await feature.load()
            }
        }
    }

    private var filtersActive: Bool {
        feature.filterKind != nil || feature.filterEvaluationState != nil || feature.filterTrash != .hide
    }

    private var gridView: some View {
        ScrollView {
            LazyVGrid(
                columns: [GridItem(.adaptive(minimum: 120), spacing: 8)],
                spacing: 8
            ) {
                ForEach(feature.items) { item in
                    MediaCell(item: item)
                        .onTapGesture {
                            selectedItem = item
                            showingViewer = true
                        }
                        .onAppear {
                            feature.loadMoreIfNeeded(currentItem: item)
                        }
                }
            }
            .padding(12)
        }
    }
}
