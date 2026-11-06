import SwiftUI

struct MediaInfoSheet: View {
    let item: MobileMediaSummary
    let openPrompt: (PromptUsageScope) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var feature: MediaInfoFeature

    init(item: MobileMediaSummary, apiClient: APIClient, openPrompt: @escaping (PromptUsageScope) -> Void) {
        self.item = item
        self.openPrompt = openPrompt
        _feature = State(initialValue: MediaInfoFeature(apiClient: apiClient))
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    if let filename = item.originalFilename { Text(filename).font(.headline).textSelection(.enabled) }
                    if let date = item.fileDate { LabeledContent("文件日期") { Text(date, format: .dateTime.year().month().day().hour().minute()) } }
                    LabeledContent("类型", value: item.kind == .image ? "照片" : "视频")
                    if let width = item.width, let height = item.height { LabeledContent("尺寸", value: "\(width) × \(height)") }
                    if let duration = item.durationLabel { LabeledContent("时长", value: duration) }
                    if let bytes = item.byteSize { LabeledContent("原始文件", value: bytes.formatted(.byteCount(style: .file))) }
                }
                Section("Prompt ID") {
                    if let id = feature.workflow?.promptID, !id.isEmpty {
                        Button { openPrompt(PromptUsageScope(promptID: id)); dismiss() } label: {
                            HStack { Text(id).textSelection(.enabled); Spacer(); Image(systemName: "chevron.right") }
                        }.accessibilityHint("在词库中查看使用此 Prompt 的媒体")
                    } else { Text(feature.isLoading ? "正在读取…" : "未记录 Prompt ID").foregroundStyle(.secondary) }
                }
                Section("Character LoRA") { Text(feature.workflow?.characterLora ?? "未记录").textSelection(.enabled) }
                if let loras = feature.workflow?.loras, !loras.isEmpty {
                    Section { DisclosureGroup("LoRA 列表 · \(loras.count)") { ForEach(Array(loras.enumerated()), id: \.offset) { Text($0.element).font(.footnote).textSelection(.enabled) } } }
                }
                Section("Prompt Registry · Positive Prompt") {
                    if let entry = feature.registry?.entry {
                        Text(entry.prompt.isEmpty ? "注册的提示词为空" : entry.prompt).textSelection(.enabled)
                    } else { Text(feature.isLoading ? "正在查询词库…" : "未注册或没有可用的词库定义").foregroundStyle(.secondary) }
                }
                if let error = feature.errorMessage {
                    Section { Text(error).foregroundStyle(.red); Button("重试") { Task { await feature.load(id: item.id) } } }
                }
            }
            .navigationTitle("媒体详情").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
            .task { await feature.load(id: item.id) }
        }
        .presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }
}
