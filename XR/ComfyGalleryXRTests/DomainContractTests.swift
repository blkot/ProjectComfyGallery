import Foundation
import XCTest
@testable import ComfyGalleryXR

final class DomainContractTests: XCTestCase {
    func testNarrowMediaDTOIgnoresPrivateAdditiveFields() throws {
        let id = UUID()
        let json = """
        {
          "id": "\(id.uuidString)",
          "kind": "image",
          "status": "ready",
          "mime_type": "image/png",
          "width": 1024,
          "height": 1536,
          "duration_seconds": null,
          "byte_size": 5000,
          "is_trash": false,
          "preview_url": "/api/v1/media/\(id.uuidString)/preview",
          "original_filename": "private.png",
          "sha256": "private-hash",
          "workflow_status": "parsed",
          "prompt": "private prompt"
        }
        """
        let item = try JSONDecoder().decode(XRMediaSummary.self, from: Data(json.utf8))
        XCTAssertEqual(item.id, id)
        XCTAssertEqual(item.kind, .image)
        XCTAssertEqual(item.width, 1024)
        XCTAssertFalse(item.favorite)
        XCTAssertFalse(item.spatialViewPreferred)
    }

    func testUnknownKindIsRepresentableWithoutCrashing() throws {
        let json = """
        {
          "id": "\(UUID().uuidString)",
          "kind": "model3d",
          "status": "ready",
          "mime_type": "model/usdz",
          "width": null,
          "height": null,
          "duration_seconds": null,
          "byte_size": 5000,
          "is_trash": false,
          "preview_url": "/preview"
        }
        """
        let item = try JSONDecoder().decode(XRMediaSummary.self, from: Data(json.utf8))
        XCTAssertEqual(item.kind, .unsupported("model3d"))
    }

    func testSpatialEligibilityBoundaries() {
        XCTAssertEqual(
            SpatialEligibility.evaluate(kind: .image, width: 320, height: 960),
            .eligible
        )
        XCTAssertEqual(
            SpatialEligibility.evaluate(kind: .image, width: 319, height: 960),
            .unavailable("The shortest side must be at least 320 pixels.")
        )
        XCTAssertEqual(
            SpatialEligibility.evaluate(kind: .image, width: 16_385, height: 8_000),
            .unavailable("The longest side must be 16,384 pixels or less.")
        )
        XCTAssertNotEqual(
            SpatialEligibility.evaluate(kind: .video, width: 1920, height: 1080),
            .eligible
        )
    }

    func testMediaPreferenceFieldsDecodeAndEnforceSpatialFavoriteInvariant() throws {
        let json = """
        {
          "id": "\(UUID().uuidString)",
          "kind": "image",
          "status": "ready",
          "mime_type": "image/png",
          "width": 1024,
          "height": 1536,
          "duration_seconds": null,
          "byte_size": 5000,
          "is_trash": false,
          "preview_url": "/preview",
          "spatial_view_preferred": true,
          "favorite": false
        }
        """
        let item = try JSONDecoder().decode(XRMediaSummary.self, from: Data(json.utf8))
        let normalized = item.preferences.enforcingSpatialFavoriteInvariant

        XCTAssertTrue(normalized.spatialViewPreferred)
        XCTAssertTrue(normalized.favorite)
    }

    func testLegacyGalleryScopeDefaultsToAllPreferenceFilter() throws {
        let json = """
        {
          "kind": "images",
          "includesTrash": false,
          "sort": "file_created_desc"
        }
        """
        let scope = try JSONDecoder().decode(GalleryScope.self, from: Data(json.utf8))

        XCTAssertEqual(scope.kind, .images)
        XCTAssertEqual(scope.preference, .all)
        XCTAssertEqual(scope.sort, .newest)
    }

    func testPreferenceMutationOrderingPreservesInvariantAcrossPartialWrites() {
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                kind: .image,
                desired: MediaPreferences(
                    favorite: false,
                    spatialViewPreferred: true
                )
            ),
            [.favorite(true), .spatial(true)]
        )
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                kind: .image,
                desired: MediaPreferences(
                    favorite: false,
                    spatialViewPreferred: false
                )
            ),
            [.spatial(false), .favorite(false)]
        )
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                kind: .video,
                desired: MediaPreferences(
                    favorite: true,
                    spatialViewPreferred: false
                )
            ),
            [.favorite(true)]
        )
    }
}
