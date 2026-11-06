import Foundation
import Observation

@MainActor
@Observable
final class MediaInfoFeature {
    private(set) var workflow: MediaWorkflowSummary?
    private(set) var registry: PromptRegistryLookup?
    private(set) var isLoading = false
    var errorMessage: String?
    private let apiClient: APIClient
    init(apiClient: APIClient) { self.apiClient = apiClient }

    func load(id: String) async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        workflow = nil
        registry = nil
        defer { isLoading = false }
        do {
            workflow = try await apiClient.request(.mediaWorkflow(id: id))
            if let prompt = workflow?.promptID, !prompt.isEmpty {
                registry = try await apiClient.request(.promptLookup(scope: PromptUsageScope(promptID: prompt), limit: 1, offset: 0))
            }
        } catch { if !Task.isCancelled { errorMessage = error.localizedDescription } }
    }
}
