import Foundation
import Observation

@MainActor
@Observable
final class PromptRegistryFeature {
    var directID = ""
    var source = ""
    var index = ""
    var character: String?
    private(set) var sources: [String] = []
    private(set) var lookup: PromptRegistryLookup?
    private(set) var activeScope: PromptUsageScope?
    private(set) var isLoading = false
    var errorMessage: String?
    var sourceError: String?
    let library: LibraryFeature
    private let apiClient: APIClient
    private var generation = 0

    init(apiClient: APIClient) {
        self.apiClient = apiClient
        library = LibraryFeature(service: LiveGalleryService(apiClient: apiClient))
    }

    func loadSources() async {
        do {
            try await Task.sleep(for: .milliseconds(250))
            let result: [String] = try await apiClient.request(.promptSources(query: source))
            try Task.checkCancellation()
            sources = result
            sourceError = nil
        } catch { if !Task.isCancelled { sourceError = error.localizedDescription } }
    }

    func openDirect() async {
        let id = directID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }
        await open(PromptUsageScope(promptID: id, characterLora: character))
    }

    func openStructured() async {
        guard let id = PromptUsageScope.identifier(source: source, index: index) else {
            errorMessage = "请输入 Source 与纯数字 Index；前导零会保留。"
            return
        }
        await open(PromptUsageScope(promptID: id, characterLora: character))
    }

    func changeCharacter() async {
        guard var scope = activeScope, scope.characterLora != character else { return }
        scope.characterLora = character
        await open(scope)
    }

    func open(_ scope: PromptUsageScope) async {
        generation += 1
        let request = generation
        activeScope = scope
        directID = scope.promptID
        character = scope.characterLora
        lookup = nil
        errorMessage = nil
        isLoading = true
        library.scope = GalleryScope(promptUsage: scope)
        defer { if request == generation { isLoading = false } }
        async let page: Void = library.reload(preservingPosition: true)
        do {
            let result: PromptRegistryLookup = try await apiClient.request(.promptLookup(scope: scope, limit: 1, offset: 0))
            try Task.checkCancellation()
            if request == generation { lookup = result }
        } catch { if request == generation, !Task.isCancelled { errorMessage = error.localizedDescription } }
        await page
    }
}
