import Foundation
import XCTest
@testable import ComfyGalleryXR

final class GalleryPlayableMediaTests: XCTestCase {
    override func tearDown() {
        TestURLProtocol.handler = nil
        super.tearDown()
    }

    func testPageRequestDoesNotExcludeWarningStatus() async throws {
        TestURLProtocol.handler = { request in
            guard Self.queryValue(named: "status", in: request) == nil else {
                return try Self.response(
                    for: request,
                    statusCode: 400,
                    json: Self.errorJSON(message: "A single ready status excludes warning media.")
                )
            }
            return try Self.response(
                for: request,
                json: Self.pageJSON(
                    items: [Self.summaryJSON(id: UUID(), status: "ready_with_warnings")],
                    total: 1,
                    limit: 48,
                    offset: 0
                )
            )
        }
        let repository = try await makeRepository()

        let page = try await repository.page(scope: GalleryScope(), offset: 0)

        XCTAssertEqual(page.items.map(\.status), ["ready_with_warnings"])
    }

    func testPageAccumulatorIncludesOnlyPlayableStatusesAndPreservesRawOffset() {
        let ready = summary(status: "ready")
        let warning = summary(status: "ready_with_warnings")
        let processing = summary(status: "processing")
        let page = MediaPage(
            items: [ready, warning, processing],
            total: 3,
            limit: 3,
            offset: 0
        )

        let result = MediaPageAccumulator.accumulate(
            existing: [],
            page: page,
            replacing: true
        )

        XCTAssertEqual(result.items.map(\.id), [ready.id, warning.id])
        XCTAssertEqual(result.rawOffset, 3)
        XCTAssertTrue(result.isExhausted)
    }

    func testNavigationSkipsNonPlayableNeighbor() async throws {
        let currentID = UUID()
        let processingID = UUID()
        let warningID = UUID()
        TestURLProtocol.handler = { request in
            guard Self.queryValue(named: "status", in: request) == nil else {
                return try Self.response(
                    for: request,
                    statusCode: 400,
                    json: Self.errorJSON(message: "Navigation must use the raw ordered stream.")
                )
            }

            switch request.url?.path {
            case "/api/v1/media/\(currentID.uuidString.lowercased())/navigation":
                return try Self.response(
                    for: request,
                    json: Self.navigationJSON(
                        mediaID: currentID,
                        position: 1,
                        total: 3,
                        previousID: nil,
                        nextID: processingID
                    )
                )
            case "/api/v1/media/\(processingID.uuidString.lowercased())":
                return try Self.response(
                    for: request,
                    json: Self.detailJSON(id: processingID, status: "processing")
                )
            case "/api/v1/media/\(processingID.uuidString.lowercased())/navigation":
                return try Self.response(
                    for: request,
                    json: Self.navigationJSON(
                        mediaID: processingID,
                        position: 2,
                        total: 3,
                        previousID: currentID,
                        nextID: warningID
                    )
                )
            case "/api/v1/media/\(warningID.uuidString.lowercased())":
                return try Self.response(
                    for: request,
                    json: Self.detailJSON(id: warningID, status: "ready_with_warnings")
                )
            default:
                return try Self.response(
                    for: request,
                    statusCode: 404,
                    json: Self.errorJSON(message: "Unexpected test request.")
                )
            }
        }
        let repository = try await makeRepository()

        let navigation = try await repository.navigation(id: currentID, scope: GalleryScope())

        XCTAssertEqual(navigation.nextID, warningID)
        XCTAssertEqual(navigation.nextPosition, 3)
    }

    func testPlayablePagesBackfillsPastRawPageWithoutVisibleMedia() async throws {
        let warningID = UUID()
        TestURLProtocol.handler = { request in
            let offset = Int(Self.queryValue(named: "offset", in: request) ?? "0")
            switch offset {
            case 0:
                return try Self.response(
                    for: request,
                    json: Self.pageJSON(
                        items: [Self.summaryJSON(id: UUID(), status: "processing")],
                        total: 2,
                        limit: 1,
                        offset: 0
                    )
                )
            case 1:
                return try Self.response(
                    for: request,
                    json: Self.pageJSON(
                        items: [Self.summaryJSON(id: warningID, status: "ready_with_warnings")],
                        total: 2,
                        limit: 1,
                        offset: 1
                    )
                )
            default:
                return try Self.response(
                    for: request,
                    statusCode: 404,
                    json: Self.errorJSON(message: "Unexpected page offset.")
                )
            }
        }
        let repository = try await makeRepository()

        let pages = try await repository.playablePages(
            scope: GalleryScope(),
            visibleLimit: 1,
            offset: 0
        )
        let result = pages.reduce(
            MediaPageAccumulationResult(items: [], rawOffset: 0, isExhausted: false)
        ) { partial, page in
            MediaPageAccumulator.accumulate(
                existing: partial.items,
                page: page,
                replacing: page.offset == 0
            )
        }

        XCTAssertEqual(pages.count, 2)
        XCTAssertEqual(result.items.map(\.id), [warningID])
        XCTAssertEqual(result.rawOffset, 2)
        XCTAssertTrue(result.isExhausted)
    }

    private func makeRepository() async throws -> GalleryRepository {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [TestURLProtocol.self]
        let api = APIClient(session: URLSession(configuration: configuration))
        let baseURL = try XCTUnwrap(URL(string: "https://gallery.example"))
        await api.configure(
            profile: ServerProfile(baseURL: baseURL),
            token: "test-token"
        )
        return GalleryRepository(api: api)
    }

    private func summary(status: String) -> XRMediaSummary {
        XRMediaSummary(
            id: UUID(),
            kind: .image,
            status: status,
            mimeType: "image/png",
            width: 1_024,
            height: 1_536,
            durationSeconds: nil,
            byteSize: 1_000,
            isTrash: false,
            previewPath: "/preview"
        )
    }

    private static func queryValue(named name: String, in request: URLRequest) -> String? {
        guard let url = request.url else { return nil }
        return URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?
            .first(where: { $0.name == name })?
            .value
    }

    private static func response(
        for request: URLRequest,
        statusCode: Int = 200,
        json: String
    ) throws -> (HTTPURLResponse, Data) {
        let url = try XCTUnwrap(request.url)
        let response = try XCTUnwrap(HTTPURLResponse(
            url: url,
            statusCode: statusCode,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        ))
        return (response, Data(json.utf8))
    }

    private static func errorJSON(message: String) -> String {
        """
        {"error":{"code":"TEST_FAILURE","message":"\(message)","details":{},"request_id":"test"}}
        """
    }

    private static func pageJSON(
        items: [String],
        total: Int,
        limit: Int,
        offset: Int
    ) -> String {
        """
        {"items":[\(items.joined(separator: ","))],"total":\(total),"limit":\(limit),"offset":\(offset)}
        """
    }

    private static func summaryJSON(id: UUID, status: String) -> String {
        """
        {"id":"\(id.uuidString.lowercased())","kind":"image","status":"\(status)","mime_type":"image/png","width":1024,"height":1536,"duration_seconds":null,"byte_size":1000,"is_trash":false,"preview_url":"/preview","spatial_available":false,"prefer_spatial_playback":false,"favorite":false}
        """
    }

    private static func detailJSON(id: UUID, status: String) -> String {
        """
        {"id":"\(id.uuidString.lowercased())","kind":"image","status":"\(status)","mime_type":"image/png","width":1024,"height":1536,"duration_seconds":null,"byte_size":1000,"is_trash":false,"preview_url":"/preview","playback_url":"/playback","original_url":"/original","spatial_available":false,"variants":[],"prefer_spatial_playback":false,"favorite":false}
        """
    }

    private static func navigationJSON(
        mediaID: UUID,
        position: Int,
        total: Int,
        previousID: UUID?,
        nextID: UUID?
    ) -> String {
        let previous = previousID.map { "\"\($0.uuidString.lowercased())\"" } ?? "null"
        let next = nextID.map { "\"\($0.uuidString.lowercased())\"" } ?? "null"
        let previousPosition = previousID == nil ? "null" : String(position - 1)
        let nextPosition = nextID == nil ? "null" : String(position + 1)
        return """
        {"media_id":"\(mediaID.uuidString.lowercased())","position":\(position),"total":\(total),"previous_id":\(previous),"previous_position":\(previousPosition),"next_id":\(next),"next_position":\(nextPosition)}
        """
    }
}
