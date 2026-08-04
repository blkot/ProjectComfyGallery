# Native visionOS Development Handoff

**Status:** Implementation plan for an independent visionOS engineer or coding agent

**Target:** visionOS 26.0+

**Toolchain:** Stable Xcode with visionOS 26 SDK, Swift 6, Apple-silicon Mac

## Technical direction

Build a native SwiftUI visionOS app.

Use:

- SwiftUI for scenes, windows, grid, ornaments, gestures, and restoration.
- RealityKit for 2D image presentation and generated spatial scenes.
- AVKit/AVFoundation for video.
- URLSession for authenticated JSON and media downloads.
- Keychain Services for the bearer token.
- SwiftData for server profile, Library state, cache index, and last selected media.
- ImageIO for display-sized image downsampling.
- OSLog/signposts for redacted performance diagnostics.
- XCTest/XCUITest plus physical-device exploratory tests.

No Reality Composer Pro asset is required for the windowed MVP. No third-party
networking, image, architecture, or gesture framework is required.

## Suggested repository layout

Create the app below `XR/`:

```text
XR/
├─ ComfyGalleryXR.xcodeproj
├─ ComfyGalleryXR/
│  ├─ App/
│  │  ├─ ComfyGalleryXRApp.swift
│  │  ├─ AppEnvironment.swift
│  │  └─ SceneRoute.swift
│  ├─ Core/
│  │  ├─ API/
│  │  ├─ Auth/
│  │  ├─ Cache/
│  │  ├─ Media/
│  │  ├─ Persistence/
│  │  └─ Support/
│  ├─ Features/
│  │  ├─ Connection/
│  │  ├─ Library/
│  │  └─ MediaViewer/
│  ├─ Spatial/
│  │  ├─ SpatialImageController.swift
│  │  ├─ SpatialImageView.swift
│  │  └─ ImagePresentationScaler.swift
│  ├─ Video/
│  │  ├─ PlayerController.swift
│  │  └─ PlayerViewControllerRepresentable.swift
│  ├─ DesignSystem/
│  └─ Resources/
├─ ComfyGalleryXRTests/
├─ ComfyGalleryXRUITests/
└─ Fixtures/
```

Do not modify or couple to the separate `mobile/` Xcode project. Share concepts by
contract; extract a shared Swift package only after both clients contain proven
duplicate code and compatible deployment requirements.

## Scene architecture

Use stable scene IDs and one shared observable app model.

Conceptual declaration:

```swift
@main
struct ComfyGalleryXRApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        Window("Gallery", id: SceneID.library) {
            LibraryView()
                .environment(model)
        }
        .defaultSize(width: 1180, height: 760)
        .windowResizability(.contentMinSize)
        .restorationBehavior(.automatic)

        Window("Media", id: SceneID.viewer) {
            MediaViewerView()
                .environment(model)
        }
        .defaultSize(width: 900, height: 700)
        .windowResizability(.contentMinSize)
        .restorationBehavior(.automatic)
        .defaultLaunchBehavior(.suppressed)

        Window("Connect", id: SceneID.connection) {
            ConnectionView()
                .environment(model)
        }
        .windowResizability(.contentSize)
        .restorationBehavior(.disabled)
    }
}
```

Treat this as structure, not copy-paste authority; confirm exact SDK signatures in
the installed visionOS 26 SDK.

Opening media:

1. Update shared `ViewerSelection` with media ID and Library scope.
2. Call `openWindow(id: SceneID.viewer)`.
3. If the Viewer already exists, update its content rather than creating a second
   scene.
4. Optionally use `defaultWindowPlacement` to suggest a trailing placement relative
   to Library on first open.

The system/user owns final placement. Do not reposition an already placed card in
response to navigation.

## Persistent spatial UI

- Keep `.restorationBehavior(.automatic)` on Library and Viewer.
- Store filter/sort, scroll anchor, selected media ID, and server profile.
- Mark Connect as nonrestorable.
- Use stable scene identity so system snapping/locking can restore the correct
  content.
- If selected media no longer exists, restore the Viewer shell with an unavailable
  state and actions to close or navigate.
- `surfaceSnappingInfo` and `UIWantsDetailedSurfaceInfo` are unnecessary unless a
  later design adapts to the detected physical surface.

No ARKit session or `WorldAnchor` belongs in this milestone.

## Architecture

```text
SwiftUI action / scene event
        ↓
@MainActor feature model
        ↓
Repository actor
        ↓
APIClient / MediaCache / SwiftData
        ↓
Narrow DTO or local resource
        ↓
Feature state + prefetch coordinator
```

Long-lived services:

- `APIClient` actor: same-origin resolution, bearer injection, JSON/error decoding,
  downloads, cancellation.
- `GalleryRepository` actor: pages, deduplication, filters, detail, navigation.
- `MediaRepository` actor: preview/original/playback cache and ImageIO decoding.
- `ViewerPrefetchCoordinator` actor: current/next/previous priority and cancellation.
- `SpatialImageController` isolated controller: RealityKit component/entity and one
  generation task.
- `PlayerController` on the main actor: one active AVPlayer and lifecycle observers.
- `CredentialStore`: Keychain token keyed by server profile.

Views do not perform URLSession requests directly.

## Domain model

Define narrow types:

- `ServerProfile`
- `Health`
- `AuthenticatedUser`
- `GalleryScope`
- `MediaPage`
- `XRMediaSummary`
- `XRMediaDetail`
- `XRMediaVariant`
- `VideoPlaybackSource`
- `MediaNavigation`
- `CachedResource`
- `ViewerSelection`
- `SpatialGenerationState`
- `APIErrorEnvelope`

`GalleryScope` contains only query semantics needed to reconstruct navigation:

- kind;
- Trash inclusion;
- sort;
- any future visual-only filter;
- a stable local scope ID.

Do not include filename, workflow, model, prompt, registry, or source data in XR
domain models.

## Library implementation

- Use `ScrollView` and `LazyVGrid`.
- Compute adaptive columns from available width; avoid manually placing cards in
  RealityKit.
- Apply system `hoverEffect` and an appropriate hover content shape.
- Use stable media UUID for `ForEach`.
- Keep a page state machine:
  - idle;
  - initial loading;
  - loaded;
  - loading next;
  - failed next;
  - exhausted.
- Start next-page load near the final two rows.
- Cancel/restart when scope changes.
- Deduplicate IDs without changing raw offset progression.
- Preserve scroll anchor through `ScrollPosition`/scene state appropriate to the
  installed SDK.

Do not load originals for grid cards.

## Authenticated image pipeline

`AsyncImage` is insufficient because the app needs bearer headers, explicit
downsampling, cancellation, and a bounded cache.

1. Download preview through `APIClient`.
2. Validate MIME and response length.
3. Downsample through ImageIO to the requested pixel size.
4. Keep decoded display images in `NSCache`.
5. Keep encoded preview/original bytes in an LRU disk cache.
6. Cancel cell tasks outside the prefetch window.
7. Release decoded images on memory pressure.

Cache keys use server profile + media UUID + resource kind, never filename.

## Video implementation

Apple recommends `AVPlayerViewController` for windowed visionOS playback. Wrap it for
SwiftUI only where necessary.

1. Display the cached poster immediately.
2. Decode canonical `spatial_available`, `prefer_spatial_playback`, and active ready
   `variants[]`; use the legacy preference alias only as a decode fallback.
3. Select a ready `spatial_video` `content_url` only when both preference and
   availability are true. Any missing or inconsistent condition selects ordinary
   `playback_url`.
4. Download the selected path through authenticated URLSession.
5. Atomically cache ordinary video by media UUID and spatial video by media plus
   variant UUID. Map `video/quicktime` to `.mov`.
6. Create an `AVPlayerItem` and install it in the one Viewer `AVPlayer`.
7. Keep `AVPlayerViewController.requiresMonoscopicViewingMode` false so valid
   MV-HEVC spatial metadata is permitted, but do not treat that property as an
   instruction to present spatially.
8. Configure `experienceController.allowedExperiences = .recommended()`.
9. For a selected spatial variant, transition to `.expanded` and call `play()` only
   after `.completed`; for ordinary video, reconcile to `.embedded` before play.
10. For an ordinary/spatial preference switch, keep the Viewer `AVPlayer` and
    `AVPlayerViewController`, replace only the current item, and preserve Loop.
11. Serialize source/experience transitions and identity-check completions so an
    obsolete transition cannot start the wrong current item.
12. Remove the poster as soon as the AVKit surface exists and let that surface fill
    the media region without an app-defined inset.
13. Pause and detach the old item before navigation commits, and return the
    experience to `.embedded` when dismantling the player.
14. Implement infinite looping without replacing the `AVPlayer`, so toggling Loop
    does not discard the active spatial experience.
15. Remove time/status observers on replacement and deinit.
16. Pause when scene phase becomes inactive.

Only the active player has audio. Prefetch downloads never instantiate playing
players. Use the selected source's byte size for the prefetch budget.

The deployed variant content endpoint supports byte ranges. If device testing proves
full authenticated download too slow, add an authenticated AVFoundation resource
loader against that contract. Do not inject tokens into URLs or rely on undocumented
AVFoundation HTTP-header options.

## Viewer navigation and prefetch

### Resolve neighbors

For every stable selection:

1. Fetch `/media/{id}/navigation` with the exact `GalleryScope`.
2. Record previous/next IDs and positions.
3. Fetch missing narrow detail for both neighbors.
4. Prepare next, then previous within budget.

This operates independently of loaded Library pages.

### Drag state machine

```text
idle
  → tracking(direction, translation)
  → canceled → idle
  → committed(targetID)
       → loading/ready target
       → selected
       → idle
```

- Filter for primarily horizontal movement.
- Predict the end translation/velocity.
- Commit at one threshold only.
- Disable a direction with no neighbor.
- Ignore navigation gestures originating in player controls or ornaments.
- Buttons invoke the same `navigate(to:)` command.
- Cancel obsolete selection and prefetch tasks by token/generation ID.

Navigation does not move or recreate the Viewer window.

## RealityKit spatial-image implementation

### Preparation

- Use the original image local file when available.
- Validate dimensions/aspect before offering the action.
- Hold one `Entity` with an `ImagePresentationComponent`.
- Display ordinary mode first.

Conceptual flow:

```swift
let spatialImage =
    try await ImagePresentationComponent.Spatial3DImage(contentsOf: localURL)

var component = ImagePresentationComponent(spatial3DImage: spatialImage)
component.desiredViewingMode = .mono
contentEntity.components.set(component)

// After explicit Make Spatial:
component.desiredViewingMode = .spatial3D
contentEntity.components.set(component)
try await spatialImage.generate()
```

Confirm exact SDK isolation/signatures in Xcode. The installed Apple sample
“Presenting images in RealityKit” is the implementation reference.

### RealityView sizing

Wrap `RealityView` in `GeometryReader3D`. In the update closure:

- observe `presentationScreenSize`;
- convert available bounds into scene coordinates;
- calculate uniform scale preserving component aspect ratio;
- keep the image presentation flush with the intended card plane; and
- recompute on window resize and viewing-mode transition.

Do not apply extra depth to text or ornaments.

### State and cancellation

`SpatialGenerationState`:

- unavailable;
- ready2D;
- generating;
- spatial;
- failed(message).

Keep the generation `Task`. Cancel it on:

- navigation;
- card close;
- disconnect;
- sustained scene inactivity; or
- explicit Cancel.

Verify the selected media ID before applying completion. A late task may never
replace a newly selected image.

Offer Disable Spatial by setting `desiredViewingMode = .mono`, clearing both
Favorite and `prefer_spatial_playback`, and evicting that generated object after
both writes succeed. Successful generation or re-enabling a cached spatial image
sets both fields to true. This coupling is an XR runtime-image interaction policy,
not a backend storage invariant. Favorite remains independently editable between
these actions; each spatial action overwrites both values regardless of their
current state.
Other generated objects may stay in a tiny in-memory LRU for the session, but no
persistent/exportable representation is assumed.

## Security and network configuration

- Add `NSLocalNetworkUsageDescription`.
- Prefer HTTPS through a trusted NAS reverse proxy.
- If private-IP HTTP is supported, use the narrowest practical App Transport
  Security policy and document the risk.
- Store tokens in Keychain with a device-only accessibility class.
- Use a dedicated URLSession and application-managed cache.
- Reject relative media URLs that resolve to a different origin.
- Redact tokens, file bodies, URLs, and private media data from OSLog.
- No analytics or third-party crash upload in MVP.

## Performance and lifecycle

- Bound preview concurrency at four.
- Run one full-media current load and at most two neighbor preparations.
- Run one spatial generation task.
- Use task priorities: current user initiated, drag-direction neighbor high, opposite
  neighbor utility, grid prefetch background.
- Pause/cancel prefetch when the relevant scene is inactive.
- Release non-visible RealityKit entities and AVPlayers on pressure.
- Instrument:
  - initial page latency;
  - preview decode latency;
  - card open-to-first-pixel;
  - video open-to-play;
  - navigation ready rate;
  - cache hit rate;
  - spatial generation time/failure/cancellation;
  - peak resident memory.

Never log media IDs alongside private content in production diagnostics.

## Testing

### Unit

- Base URL normalization and same-origin resolution.
- Token redaction.
- DTO additive-field tolerance.
- Offset paging and duplicate ID handling.
- Navigation query reconstruction from `GalleryScope`.
- Prefetch priority/cancellation.
- Drag threshold, velocity, direction, and single-commit behavior.
- Cache LRU/budget and atomic failure cleanup.
- Canonical preference decoding with legacy fallback.
- Runtime spatial-image Favorite/preference coupling and spatial-video preference
  independence.
- Spatial-video selection truth table and ordinary fallback.
- Spatial-video expanded transition before autoplay, embedded return for 2D, and
  stale-transition cancellation across source replacement.
- Loop toggling preserves the active `AVPlayer` and presentation request.
- Variant-safe cache identity and QuickTime `.mov` mapping.
- Spatial eligibility constraints.
- Late spatial-generation result ignored after selection change.

### Contract/integration

Run against the Mac-local Compose environment:

- health + token verification;
- list mixed/image/video pages;
- navigation across a page boundary;
- detail/preview/playback/original download;
- 401, 404, and 5xx recovery;
- server restart with cached visible content.

Use `uv` for repository Python helpers. Never point automated tests at NAS production.

### Simulator

- Connect and Library layouts.
- Window resize and multi-scene state.
- Grid hover/tap/paging.
- Viewer drag/buttons.
- Image and local video presentation.
- accessibility identifiers and Reduce Motion.
- Spatial generation error/unavailable UI only.

### Physical Vision Pro

Required:

- gaze target comfort and hover behavior;
- look-pinch-drag tuning;
- AVKit controls and gesture conflict;
- local MV-HEVC recognition and automatic spatial presentation;
- ordinary/spatial preference switching and unavailable-variant fallback;
- authenticated byte-range playback if the streaming follow-up is implemented;
- surface snap/lock/restoration;
- dynamic window scale and placement;
- audio lifecycle;
- `Spatial3DImage.generate()` success/failure/cancel;
- spatial/2D switching and visual comfort;
- memory/thermal behavior during repeated viewing.

## Delivery phases

### XR-M0 — Skeleton and connection

- visionOS 26 Xcode project.
- scene inventory and shared environment.
- URL/token onboarding, health/session validation, Keychain.
- automated build/unit-test workflow.

### XR-M1 — Spatial Library

- restorable/resizable Library window.
- paginated grid and hover/tap.
- authenticated preview pipeline.
- filters, errors, cache, scroll restoration.

### XR-M2 — Media card

- single Viewer scene and suggested placement.
- image contain/resizing.
- authenticated AVKit video playback and auto-play lifecycle.
- viewer restoration and unavailable state.

### XR-M3 — Continuous navigation

- backend navigation endpoint integration.
- buttons plus look-pinch-drag.
- neighbor detail/media prefetch.
- page-boundary and changing-population behavior.
- network loss and memory-pressure hardening.

### XR-M4 — Make Spatial

- original-image cache.
- eligibility preflight.
- RealityKit presentation and scaling.
- generate/cancel/2D fallback.
- physical-device quality and artifact tests.

### XR-M5 — Polish and release

- surface lock/restoration verification.
- accessibility and Reduce Motion.
- privacy/log audit.
- performance budgets and long browsing run.
- installation/distribution documentation.

## Definition of done

- All product acceptance scenarios pass.
- The app uses Shared Space with no unnecessary ARKit permission.
- Library and Viewer restore where system behavior allows.
- One Media card only.
- No visible metadata inspector or token leakage.
- Pagination and navigation cross boundaries without forcing a return to Library.
- Videos auto-play only when active and stop reliably.
- Ready preferred spatial videos use their variant while all inconsistent or
  unavailable states fall back to ordinary playback.
- Backend preference fields and spatial-video playback controls remain independent;
  runtime spatial-image enable/disable intentionally updates both fields.
- Neighbor prefetch remains bounded under a long session.
- Spatial generation works on physical hardware and always retains 2D fallback.
- Simulator and device test responsibilities are documented.
- No change is required to NAS production data for automated testing.

## Evidence-driven follow-ups

Only expand after measurement:

- read-only API token scopes;
- signed/streaming playback URLs;
- cursor-based media pagination;
- multiple pinned cards;
- spatial HEIC ingestion;
- `.spatial3DImmersive`;
- custom environments;
- SharePlay;
- evaluation/review in XR; or
- ARKit world-anchor content in a Full Space.
