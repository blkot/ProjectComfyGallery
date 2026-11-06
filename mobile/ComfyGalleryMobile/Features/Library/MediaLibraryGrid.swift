import SwiftUI

struct MediaLibraryGrid: View {
    @Bindable var feature: LibraryFeature
    let width: CGFloat
    let open: (MobileMediaSummary) -> Void
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        let count = LibraryLayout.columnCount(width: width, accessibilitySize: dynamicTypeSize.isAccessibilitySize)
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: LibraryLayout.spacing), count: count), spacing: LibraryLayout.spacing) {
            ForEach(feature.sections) { section in
                Section {
                    ForEach(section.items) { item in
                        Button {
                            if feature.isSelecting { feature.toggleSelection(item.id) }
                            else { feature.returnAnchorID = item.id; open(item) }
                        } label: { MediaCell(item: item, isSelecting: feature.isSelecting, isSelected: feature.selectedIDs.contains(item.id)) }
                        .buttonStyle(.plain).id(item.id)
                        .accessibilityHint(feature.isSelecting ? "切换选择" : "全屏查看")
                        .task { await feature.loadMoreIfNeeded(id: item.id) }
                    }
                } header: {
                    HStack {
                        Text(section.title).font(.headline)
                        Spacer()
                        Text(feature.scope.promptUsage == nil ? (feature.scope.sort == .importedNewest ? "导入日期" : "文件日期") : "Character LoRA")
                            .font(.caption).foregroundStyle(.secondary)
                    }.padding(.horizontal, 16).padding(.vertical, 10).accessibilityAddTraits(.isHeader)
                }
            }
        }
    }
}
