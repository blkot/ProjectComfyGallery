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
        XCTAssertFalse(item.spatialAvailable)
        XCTAssertFalse(item.prefersSpatialPlayback)
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

    func testCanonicalPlaybackPreferenceWinsAndFavoriteRemainsIndependent() throws {
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
          "spatial_available": false,
          "prefer_spatial_playback": true,
          "spatial_view_preferred": false,
          "favorite": false
        }
        """
        let item = try JSONDecoder().decode(XRMediaSummary.self, from: Data(json.utf8))

        XCTAssertTrue(item.prefersSpatialPlayback)
        XCTAssertFalse(item.favorite)
    }

    func testLegacyPlaybackPreferenceAliasStillDecodes() throws {
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

        XCTAssertTrue(item.prefersSpatialPlayback)
        XCTAssertFalse(item.favorite)
    }

    func testSpatialVideoSelectionRequiresPreferenceAvailabilityAndReadyVariant() throws {
        let variantID = UUID()
        let spatial = try videoDetail(
            prefersSpatial: true,
            spatialAvailable: true,
            variantID: variantID,
            variantStatus: "ready"
        )
        XCTAssertEqual(
            spatial.selectedVideoPlaybackSource?.representation,
            .spatial(variantID: variantID)
        )
        XCTAssertEqual(
            spatial.selectedVideoPlaybackSource?.path,
            "/api/v1/media/video/variants/\(variantID.uuidString)/content"
        )

        let preferenceOff = try videoDetail(
            prefersSpatial: false,
            spatialAvailable: true,
            variantID: variantID,
            variantStatus: "ready"
        )
        XCTAssertEqual(preferenceOff.selectedVideoPlaybackSource?.representation, .ordinary)

        let unavailable = try videoDetail(
            prefersSpatial: true,
            spatialAvailable: false,
            variantID: variantID,
            variantStatus: "ready"
        )
        XCTAssertEqual(unavailable.selectedVideoPlaybackSource?.representation, .ordinary)

        let notReady = try videoDetail(
            prefersSpatial: true,
            spatialAvailable: true,
            variantID: variantID,
            variantStatus: "processing"
        )
        XCTAssertEqual(notReady.selectedVideoPlaybackSource?.representation, .ordinary)
    }

    func testPreferenceMutationPlanWritesOnlyChangedIndependentFields() {
        let desired = MediaPreferences(
            favorite: false,
            prefersSpatialPlayback: true
        )
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                fields: [.favorite],
                desired: desired
            ),
            [.favorite(false)]
        )
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                fields: [.playbackPreference],
                desired: desired
            ),
            [.playbackPreference(true)]
        )
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                fields: [.favorite, .playbackPreference],
                desired: desired
            ),
            [.favorite(false), .playbackPreference(true)]
        )
    }

    func testRuntimeSpatialImageActionsIntentionallyCoupleFavoriteAndPlaybackPreference() {
        let enable = MediaPreferenceMutationPlan.runtimeSpatialImage(isEnabled: true)
        XCTAssertEqual(
            enable.preferences,
            MediaPreferences(favorite: true, prefersSpatialPlayback: true)
        )
        XCTAssertEqual(enable.fields, [.favorite, .playbackPreference])
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                fields: enable.fields,
                desired: enable.preferences
            ),
            [.favorite(true), .playbackPreference(true)]
        )

        let disable = MediaPreferenceMutationPlan.runtimeSpatialImage(isEnabled: false)
        XCTAssertEqual(
            disable.preferences,
            MediaPreferences(favorite: false, prefersSpatialPlayback: false)
        )
        XCTAssertEqual(disable.fields, [.favorite, .playbackPreference])
        XCTAssertEqual(
            MediaPreferenceMutationPlan.writes(
                fields: disable.fields,
                desired: disable.preferences
            ),
            [.favorite(false), .playbackPreference(false)]
        )
    }

    func testSpatialVideoPlaybackPreferencePreservesFavorite() {
        let enable = MediaPreferenceMutationPlan.playbackPreference(
            isPreferred: true,
            preserving: MediaPreferences(
                favorite: false,
                prefersSpatialPlayback: false
            )
        )
        XCTAssertEqual(
            enable.preferences,
            MediaPreferences(favorite: false, prefersSpatialPlayback: true)
        )
        XCTAssertEqual(enable.fields, [.playbackPreference])

        let disable = MediaPreferenceMutationPlan.playbackPreference(
            isPreferred: false,
            preserving: MediaPreferences(
                favorite: true,
                prefersSpatialPlayback: true
            )
        )
        XCTAssertEqual(
            disable.preferences,
            MediaPreferences(favorite: true, prefersSpatialPlayback: false)
        )
        XCTAssertEqual(disable.fields, [.playbackPreference])
    }

    func testFavoriteCanBeClearedIndependentlyFromRuntimeSpatialImage() {
        let spatialPreferences = MediaPreferences(
            favorite: true,
            prefersSpatialPlayback: true
        )
        let imageMutation = MediaPreferenceMutationPlan.favorite(
            isFavorite: false,
            preserving: spatialPreferences
        )
        XCTAssertEqual(
            imageMutation.preferences,
            MediaPreferences(favorite: false, prefersSpatialPlayback: true)
        )
        XCTAssertEqual(imageMutation.fields, [.favorite])

        let videoMutation = MediaPreferenceMutationPlan.favorite(
            isFavorite: false,
            preserving: spatialPreferences
        )
        XCTAssertEqual(
            videoMutation.preferences,
            MediaPreferences(favorite: false, prefersSpatialPlayback: true)
        )
        XCTAssertEqual(videoMutation.fields, [.favorite])
    }

    func testSpatialVariantCacheIdentityAndQuickTimeExtension() {
        let profileID = UUID()
        let mediaID = UUID()
        let firstVariantID = UUID()
        let secondVariantID = UUID()
        let first = MediaCacheKey(
            profileID: profileID,
            mediaID: mediaID,
            kind: .spatialVideoPlayback,
            resourceID: firstVariantID
        )
        let second = MediaCacheKey(
            profileID: profileID,
            mediaID: mediaID,
            kind: .spatialVideoPlayback,
            resourceID: secondVariantID
        )

        XCTAssertNotEqual(first.identifier, second.identifier)
        XCTAssertEqual(MediaCache.fileExtension(for: "video/quicktime"), "mov")
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

    private func videoDetail(
        prefersSpatial: Bool,
        spatialAvailable: Bool,
        variantID: UUID,
        variantStatus: String
    ) throws -> XRMediaDetail {
        let mediaID = UUID()
        let contentPath =
            "/api/v1/media/video/variants/\(variantID.uuidString)/content"
        let json = """
        {
          "id": "\(mediaID.uuidString)",
          "kind": "video",
          "status": "ready",
          "mime_type": "video/mp4",
          "width": 1920,
          "height": 1080,
          "duration_seconds": 4.33,
          "byte_size": 2000,
          "is_trash": false,
          "preview_url": "/preview",
          "playback_url": "/playback",
          "original_url": "/original",
          "favorite": false,
          "spatial_available": \(spatialAvailable),
          "prefer_spatial_playback": \(prefersSpatial),
          "variants": [
            {
              "id": "\(variantID.uuidString)",
              "role": "spatial_video",
              "status": "\(variantStatus)",
              "mime_type": "video/quicktime",
              "byte_size": 3000,
              "content_url": "\(contentPath)"
            }
          ]
        }
        """
        return try JSONDecoder().decode(XRMediaDetail.self, from: Data(json.utf8))
    }
}

@MainActor
final class VideoPlaybackExperienceTests: XCTestCase {
    func testSpatialPlaybackWaitsForExpandedExperienceBeforePlaying() async {
        let experience = ControlledVideoPlaybackExperience(current: .embedded)
        let player = RecordingVideoPlayer()
        let coordinator = VideoPlaybackExperienceCoordinator(experience: experience)

        coordinator.update(
            player: player,
            presentation: .expandedSpatial,
            shouldAutoplay: true,
            isActive: true
        )
        coordinator.setViewVisible(true)
        await waitUntil { experience.requestedPresentations == [.expandedSpatial] }

        XCTAssertEqual(player.playCount, 0)
        experience.completeNextTransition(succeeding: true)
        await waitUntil { player.playCount == 1 }

        XCTAssertEqual(player.playCount, 1)
    }

    func testOrdinaryPlaybackReturnsToEmbeddedBeforePlaying() async {
        let experience = ControlledVideoPlaybackExperience(current: .expandedSpatial)
        let player = RecordingVideoPlayer()
        let coordinator = VideoPlaybackExperienceCoordinator(experience: experience)

        coordinator.update(
            player: player,
            presentation: .embedded,
            shouldAutoplay: true,
            isActive: true
        )
        coordinator.setViewVisible(true)
        await waitUntil { experience.requestedPresentations == [.embedded] }

        XCTAssertEqual(player.playCount, 0)
        experience.completeNextTransition(succeeding: true)
        await waitUntil { player.playCount == 1 }

        XCTAssertEqual(player.playCount, 1)
    }

    func testStaleSpatialTransitionCannotStartReplacedPlayer() async {
        let experience = ControlledVideoPlaybackExperience(current: .embedded)
        let spatialPlayer = RecordingVideoPlayer()
        let ordinaryPlayer = RecordingVideoPlayer()
        let coordinator = VideoPlaybackExperienceCoordinator(experience: experience)

        coordinator.update(
            player: spatialPlayer,
            presentation: .expandedSpatial,
            shouldAutoplay: true,
            isActive: true
        )
        coordinator.setViewVisible(true)
        await waitUntil { experience.requestedPresentations == [.expandedSpatial] }

        coordinator.update(
            player: ordinaryPlayer,
            presentation: .embedded,
            shouldAutoplay: true,
            isActive: true
        )
        XCTAssertEqual(ordinaryPlayer.playCount, 0)

        experience.completeNextTransition(succeeding: true)
        await waitUntil {
            experience.requestedPresentations == [.expandedSpatial, .embedded]
        }
        XCTAssertEqual(ordinaryPlayer.playCount, 0)

        experience.completeNextTransition(succeeding: true)
        await waitUntil { ordinaryPlayer.playCount == 1 }

        XCTAssertEqual(spatialPlayer.playCount, 0)
        XCTAssertEqual(ordinaryPlayer.playCount, 1)
    }

    func testFailedExperienceTransitionDoesNotStartPlayback() async {
        let experience = ControlledVideoPlaybackExperience(current: .embedded)
        let player = RecordingVideoPlayer()
        let coordinator = VideoPlaybackExperienceCoordinator(experience: experience)

        coordinator.update(
            player: player,
            presentation: .expandedSpatial,
            shouldAutoplay: true,
            isActive: true
        )
        coordinator.setViewVisible(true)
        await waitUntil { experience.requestedPresentations == [.expandedSpatial] }

        experience.completeNextTransition(succeeding: false)
        await Task.yield()

        XCTAssertEqual(player.playCount, 0)
    }

    func testLoopingDoesNotReplaceTheSpatialAVPlayer() {
        let controller = PlayerController()
        controller.load(
            fileURL: URL(fileURLWithPath: "/tmp/spatial-loop-regression.mov"),
            autoplay: false,
            presentation: .expandedSpatial
        )
        let player = controller.player

        controller.toggleLooping()

        XCTAssertTrue(controller.isLooping)
        XCTAssertTrue(controller.player === player)
        XCTAssertEqual(controller.presentation, .expandedSpatial)
        controller.stop()
    }

    func testChangingVideoRepresentationPreservesPlayerIdentityAndLooping() {
        let controller = PlayerController()
        controller.load(
            fileURL: URL(fileURLWithPath: "/tmp/ordinary-source.mp4"),
            autoplay: false,
            presentation: .embedded
        )
        controller.toggleLooping()
        let player = controller.player

        controller.load(
            fileURL: URL(fileURLWithPath: "/tmp/spatial-source.mov"),
            autoplay: false,
            presentation: .expandedSpatial
        )

        XCTAssertTrue(controller.player === player)
        XCTAssertTrue(controller.isLooping)
        XCTAssertEqual(controller.presentation, .expandedSpatial)
        controller.stop()
    }

    func testVideoPreviewIsRemovedOnceAVKitPlayerExists() {
        XCTAssertTrue(VideoSurfaceLayerPolicy.showsPreview(hasPlayer: false))
        XCTAssertFalse(VideoSurfaceLayerPolicy.showsPreview(hasPlayer: true))
    }

    func testSpatialPreferenceToggleKeepsTheActivePlayerSessionAlive() async throws {
        let container = try PersistenceFactory.makeContainer(inMemory: true)
        let environment = try AppEnvironment(container: container)
        let model = AppModel(environment: environment)
        let profile = ServerProfile(baseURL: URL(string: "http://127.0.0.1:1")!)
        let mediaID = UUID()
        let variantID = UUID()
        let detailJSON = """
        {
          "id": "\(mediaID.uuidString)",
          "kind": "video",
          "status": "ready",
          "mime_type": "video/mp4",
          "width": 1920,
          "height": 1080,
          "duration_seconds": 4.33,
          "byte_size": 2000,
          "is_trash": false,
          "preview_url": "/preview",
          "playback_url": "/playback",
          "original_url": "/original",
          "favorite": false,
          "spatial_available": true,
          "prefer_spatial_playback": false,
          "variants": [
            {
              "id": "\(variantID.uuidString)",
              "role": "spatial_video",
              "status": "ready",
              "mime_type": "video/quicktime",
              "byte_size": 3000,
              "content_url": "/api/v1/media/video/variants/\(variantID.uuidString)/content"
            }
          ]
        }
        """

        model.activeProfile = profile
        model.viewer.detail = try JSONDecoder().decode(
            XRMediaDetail.self,
            from: Data(detailJSON.utf8)
        )
        model.viewer.selection = ViewerSelection(
            mediaID: mediaID,
            scope: GalleryScope()
        )
        model.player.load(
            fileURL: URL(fileURLWithPath: "/tmp/current-ordinary.mp4"),
            autoplay: false,
            presentation: .embedded
        )
        model.player.toggleLooping()
        let activePlayer = model.player.player

        model.toggleSpatialPlaybackForCurrentVideo()

        XCTAssertTrue(model.player.player === activePlayer)
        XCTAssertTrue(model.player.isLooping)
        await model.disconnect()
    }

    private func waitUntil(
        _ condition: @MainActor () -> Bool,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        for _ in 0..<100 {
            if condition() {
                return
            }
            await Task.yield()
        }
        XCTFail("Condition was not met.", file: file, line: line)
    }
}

@MainActor
private final class RecordingVideoPlayer: VideoPlaybackControlling {
    private(set) var playCount = 0
    private(set) var pauseCount = 0

    func play() {
        playCount += 1
    }

    func pause() {
        pauseCount += 1
    }
}

@MainActor
private final class ControlledVideoPlaybackExperience: VideoPlaybackExperienceTransitioning {
    private(set) var currentPresentation: VideoPlaybackPresentation
    private(set) var requestedPresentations: [VideoPlaybackPresentation] = []
    private var continuations: [CheckedContinuation<Bool, Never>] = []

    init(current: VideoPlaybackPresentation) {
        currentPresentation = current
    }

    func transition(to presentation: VideoPlaybackPresentation) async -> Bool {
        requestedPresentations.append(presentation)
        return await withCheckedContinuation { continuation in
            continuations.append(continuation)
        }
    }

    func completeNextTransition(succeeding: Bool) {
        guard !continuations.isEmpty else {
            XCTFail("No pending transition.")
            return
        }
        if succeeding, let requested = requestedPresentations.last {
            currentPresentation = requested
        }
        continuations.removeFirst().resume(returning: succeeding)
    }
}
