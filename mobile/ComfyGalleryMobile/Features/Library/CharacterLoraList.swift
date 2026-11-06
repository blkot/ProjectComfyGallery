import SwiftUI

struct CharacterLoraList: View {
    @Binding var selected: String?
    @State private var feature: CharacterOptionsFeature
    init(apiClient: APIClient, selected: Binding<String?>) {
        _feature = State(initialValue: CharacterOptionsFeature(apiClient: apiClient))
        _selected = selected
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("搜索 Character LoRA", text: $feature.query).textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
            Button { selected = nil } label: { Label("全部角色", systemImage: selected == nil ? "checkmark.circle.fill" : "circle").frame(maxWidth: .infinity, alignment: .leading).frame(minHeight: 44) }
            if let selected, !feature.options.contains(where: { $0.name == selected }) {
                Label(selected, systemImage: "checkmark.circle.fill").font(.subheadline).padding(.vertical, 8)
            }
            if feature.isLoading { ProgressView() }
            if let error = feature.errorMessage {
                Text(error).font(.footnote).foregroundStyle(.red)
                Button("重试加载角色") { Task { await feature.load() } }
            }
            ForEach(feature.options) { option in
                Button { selected = selected == option.name ? nil : option.name } label: {
                    HStack {
                        Image(systemName: selected == option.name ? "checkmark.circle.fill" : "circle")
                        Text(option.name).frame(maxWidth: .infinity, alignment: .leading)
                        Text(option.mediaCount.formatted()).font(.caption).foregroundStyle(.secondary)
                    }.frame(minHeight: 44)
                }.accessibilityValue(selected == option.name ? "已选择" : "未选择")
            }
            if feature.options.isEmpty && !feature.isLoading && feature.errorMessage == nil { Text("没有匹配的角色").font(.footnote).foregroundStyle(.secondary) }
            if feature.options.count == 200 { Text("显示前 200 项，输入名称可继续查找").font(.caption).foregroundStyle(.secondary) }
        }
        .task(id: feature.query) { await feature.load() }
    }
}
