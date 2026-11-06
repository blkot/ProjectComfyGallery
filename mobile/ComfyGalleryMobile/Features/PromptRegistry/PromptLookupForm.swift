import SwiftUI

struct PromptLookupForm: View {
    @Bindable var feature: PromptRegistryFeature
    let chooseCharacter: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Prompt Direct lookup").font(.headline)
            HStack {
                TextField("source - 00042", text: $feature.directID).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .onSubmit { Task { await feature.openDirect() } }
                Button("查询", systemImage: "arrow.right.circle.fill") { Task { await feature.openDirect() } }
                    .labelStyle(.iconOnly).frame(width: 44, height: 44).disabled(feature.directID.trimmingCharacters(in: .whitespaces).isEmpty)
            }.textFieldStyle(.roundedBorder)
            DisclosureGroup("Source + Index") {
                VStack(spacing: 10) {
                    HStack {
                        TextField("Source", text: $feature.source).textInputAutocapitalization(.never).autocorrectionDisabled()
                        TextField("Index", text: $feature.index).keyboardType(.numberPad).frame(maxWidth: 110)
                    }.textFieldStyle(.roundedBorder)
                    ScrollView(.horizontal, showsIndicators: false) {
                        LazyHStack { ForEach(feature.sources, id: \.self) { source in Button(source) { feature.source = source }.buttonStyle(.bordered).buttonBorderShape(.capsule) } }
                    }
                    if let error = feature.sourceError { Text("Source 建议加载失败，可直接输入。\(error)").font(.caption).foregroundStyle(.secondary) }
                    Button("按 Source + Index 加载") { Task { await feature.openStructured() } }.buttonStyle(.bordered)
                        .disabled(feature.source.isEmpty || feature.index.isEmpty)
                }.padding(.top, 10)
            }
            Button(action: chooseCharacter) {
                HStack { Label(feature.character ?? "全部 Character LoRA", systemImage: "person.crop.square"); Spacer(); Image(systemName: "chevron.right") }
                    .frame(minHeight: 44)
            }
        }
        .padding(16)
        .task(id: feature.source) { await feature.loadSources() }
    }
}
