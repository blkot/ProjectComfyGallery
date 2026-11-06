import Foundation
import Observation

@MainActor
@Observable
final class CharacterOptionsFeature {
    var query = ""
    private(set) var options: [CharacterLoraOption] = []
    private(set) var isLoading = false
    var errorMessage: String?
    private var generation = 0
    private let apiClient: APIClient
    init(apiClient: APIClient) { self.apiClient = apiClient }

    func load() async {
        generation += 1
        let request = generation
        isLoading = true
        errorMessage = nil
        defer { if request == generation { isLoading = false } }
        do {
            try await Task.sleep(for: .milliseconds(200))
            let result: [CharacterLoraOption] = try await apiClient.request(.characterLoras(query: query))
            try Task.checkCancellation()
            guard request == generation else { return }
            options = result
        } catch { if request == generation, !Task.isCancelled { errorMessage = error.localizedDescription } }
    }
}
