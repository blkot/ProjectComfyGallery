import XCTest
@testable import ComfyGalleryMobile

final class IntegrationTests: XCTestCase {
    private var apiClient: APIClient!

    override func setUp() async throws {
        try await super.setUp()
        let baseURL = URL(string: ProcessInfo.processInfo.environment["TEST_BASE_URL"] ?? "http://localhost:8181")!
        let credentialStore = CredentialStore()
        apiClient = APIClient(credentialStore: credentialStore)
        await apiClient.configure(baseURL: baseURL)
    }

    func testHealthCheck() async throws {
        let health: Health = try await apiClient.request(.health)
        XCTAssertEqual(health.status, "ok")
    }
}
