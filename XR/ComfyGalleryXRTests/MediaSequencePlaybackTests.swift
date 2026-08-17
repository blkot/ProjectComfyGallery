import AVFoundation
import XCTest
@testable import ComfyGalleryXR

@MainActor
final class MediaSequencePlaybackTests: XCTestCase {
    func testReadyImageAdvancesAfterDwell() async {
        let mediaID = UUID()
        var advancedIDs: [UUID] = []
        let controller = MediaSequencePlaybackController(
            imageDwellDuration: .zero,
            sleep: { _ in }
        )
        controller.onAdvance = { id in
            advancedIDs.append(id)
            return true
        }

        controller.start()
        controller.currentMediaDidBecomeReady(mediaID: mediaID, kind: .image)
        await waitUntil { advancedIDs == [mediaID] }

        XCTAssertTrue(controller.isEnabled)
    }

    func testVideoEndAdvancesBeforeSingleVideoLoop() {
        let mediaID = UUID()
        var advancedIDs: [UUID] = []
        let controller = MediaSequencePlaybackController()
        controller.onAdvance = { id in
            advancedIDs.append(id)
            return true
        }

        controller.start()
        controller.currentMediaDidBecomeReady(mediaID: mediaID, kind: .video)

        XCTAssertTrue(controller.videoDidReachEnd(mediaID: mediaID))
        XCTAssertEqual(advancedIDs, [mediaID])
        XCTAssertTrue(controller.isEnabled)
    }

    func testFinalVideoConsumesEndAndStopsSequence() {
        let mediaID = UUID()
        let controller = MediaSequencePlaybackController()
        controller.onAdvance = { _ in false }

        controller.start()
        controller.currentMediaDidBecomeReady(mediaID: mediaID, kind: .video)

        XCTAssertTrue(controller.videoDidReachEnd(mediaID: mediaID))
        XCTAssertFalse(controller.isEnabled)
    }

    func testFinalImageStopsSequenceAfterDwell() async {
        let mediaID = UUID()
        let controller = MediaSequencePlaybackController(
            imageDwellDuration: .zero,
            sleep: { _ in }
        )
        controller.onAdvance = { _ in false }

        controller.start()
        controller.currentMediaDidBecomeReady(mediaID: mediaID, kind: .image)
        await waitUntil { !controller.isEnabled }

        XCTAssertFalse(controller.isEnabled)
    }

    func testVideoEndFallsThroughWhenSequenceIsDisabled() {
        let mediaID = UUID()
        var didRequestAdvance = false
        let controller = MediaSequencePlaybackController()
        controller.onAdvance = { _ in
            didRequestAdvance = true
            return true
        }
        controller.currentMediaDidBecomeReady(mediaID: mediaID, kind: .video)

        XCTAssertFalse(controller.videoDidReachEnd(mediaID: mediaID))
        XCTAssertFalse(didRequestAdvance)
    }

    func testPlayFilteredCapturesCurrentGalleryScope() throws {
        let environment = try AppEnvironment(
            container: PersistenceFactory.makeContainer(inMemory: true)
        )
        let model = AppModel(environment: environment)
        let media = summary(kind: .image)
        let scope = GalleryScope(
            kind: .images,
            preference: .favorites,
            includesTrash: true,
            sort: .oldest
        )
        model.library.scope = scope
        model.library.items = [media]

        XCTAssertTrue(model.startFilteredMediaSequence())
        XCTAssertTrue(model.mediaSequence.isEnabled)
        XCTAssertEqual(
            model.viewer.selection,
            ViewerSelection(mediaID: media.id, scope: scope)
        )

        model.closeViewer()
    }

    func testManualGridSelectionStopsSequence() throws {
        let environment = try AppEnvironment(
            container: PersistenceFactory.makeContainer(inMemory: true)
        )
        let model = AppModel(environment: environment)
        let first = summary(kind: .image)
        let manual = summary(kind: .video)
        model.library.items = [first]
        XCTAssertTrue(model.startFilteredMediaSequence())

        model.select(manual)

        XCTAssertFalse(model.mediaSequence.isEnabled)
        XCTAssertEqual(model.viewer.selection?.mediaID, manual.id)
        model.closeViewer()
    }

    func testManualNextPreservesSequenceAndCapturedScope() throws {
        let environment = try AppEnvironment(
            container: PersistenceFactory.makeContainer(inMemory: true)
        )
        let model = AppModel(environment: environment)
        let currentID = UUID()
        let nextID = UUID()
        let scope = GalleryScope(kind: .videos, sort: .oldest)
        model.viewer.selection = ViewerSelection(mediaID: currentID, scope: scope)
        model.viewer.navigation = MediaNavigation(
            mediaID: currentID,
            position: 1,
            total: 2,
            previousID: nil,
            previousPosition: nil,
            nextID: nextID,
            nextPosition: 2
        )
        model.mediaSequence.start()

        XCTAssertTrue(model.navigate(.next))
        XCTAssertTrue(model.mediaSequence.isEnabled)
        XCTAssertEqual(
            model.viewer.selection,
            ViewerSelection(mediaID: nextID, scope: scope)
        )
        model.closeViewer()
    }

    func testCurrentVideoEndInvokesSequenceHook() async throws {
        let controller = PlayerController()
        var callbackCount = 0
        controller.onPlaybackEnded = {
            callbackCount += 1
            return true
        }
        controller.load(
            fileURL: URL(fileURLWithPath: "/tmp/sequence-video-end.mp4"),
            autoplay: true,
            presentation: .embedded
        )
        let item = try XCTUnwrap(controller.player?.currentItem)

        NotificationCenter.default.post(
            name: .AVPlayerItemDidPlayToEndTime,
            object: item
        )
        await waitUntil { callbackCount == 1 }

        XCTAssertEqual(callbackCount, 1)
        controller.stop()
    }

    private func summary(kind: MediaKind) -> XRMediaSummary {
        XRMediaSummary(
            id: UUID(),
            kind: kind,
            status: "ready",
            mimeType: kind == .video ? "video/mp4" : "image/png",
            width: 1_024,
            height: 1_536,
            durationSeconds: kind == .video ? 4 : nil,
            byteSize: 1_000,
            isTrash: false,
            previewPath: "/preview"
        )
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
