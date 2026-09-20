# Quest 3 development research for ComfyGallery

**Date:** 2026-09-17

**Status:** Research and proposed direction; not an accepted implementation spec.

**Evidence boundary:** Current official documentation and repository inspection. No Quest build, headset playback, workstation benchmark, or installed-toolchain verification was performed.

## Recommendation

Build a standalone Quest 3 client, with controller input as the primary interaction and ordinary image/video browsing as the complete first milestone. My recommended starting stack is **Kotlin + Jetpack Compose + Meta Spatial SDK + Android Media3/ExoPlayer**. Use the existing XR product design as a reference and retain the current gallery backend.

**Windows has the broadest Quest development tool coverage.** Its clearest advantage is headset-connected Unity Play Mode through Meta Horizon Link. **macOS is also a viable primary machine for the recommended Kotlin stack**, which uses Android build/deploy tools rather than Unity Play Mode. Since both machines are available, there is no reason to move backend/XR development away from the Mac. Use Windows for Link-based Unity evaluation if needed, and validate the standalone Android app on the physical Quest regardless of host OS. See the platform evidence below.

Keep spatial-variant playback behind a separate capability and user action. Its feasibility must not block a useful gallery app. This means the app can still use spatially placed panels while showing ordinary 2D media: spatial UI and stereoscopic media are separate features.

## Windows versus macOS

| Workflow | Windows | macOS | Consequence for this app |
| --- | --- | --- | --- |
| Unity editor and standalone Quest Android builds | Supported | Supported | Install Android Build Support and the matching SDK/NDK/JDK; the final app runs on Quest. |
| ADB deployment, logs, device testing | Supported | Supported | Either host can build, install, and test native APKs. |
| Meta Quest Developer Hub (MQDH) | Supported | Supported, including Apple silicon | Useful for device setup, logs, deployment, performance inspection, and capture. |
| Meta Horizon Link, including Unity Play-in-Editor in the headset | Supported, on a Link-compatible PC | Not supported | This is the principal Windows advantage for Unity iteration. |
| Meta XR Simulator | Supported | Supported on Apple silicon; the documented Mac distribution is ARM-only | Desktop OpenXR simulation is available on both, with feature differences. |
| Kotlin/Android Studio + Meta Spatial SDK | Supported | Supported | No documented Windows-only requirement for the basic app build/deploy loop. |
| Meta Spatial Editor and Android Studio scene opening | Supported | Supported | Visual scene composition does not determine the host choice. |

Evidence: Meta documents Windows/macOS headset development and Android APK
Build And Run; its quick start lists Unity on Windows/macOS and Android/Spatial
SDK on both. MQDH's Mac support includes M-series chips. Spatial SDK samples
explicitly list Mac or Windows and deployment through Android Studio.
[Headset development setup](https://developers.meta.com/horizon/documentation/unity/unity-env-device-setup/),
[Platform quick start](https://developers.meta.com/horizon/essentials/quick-start/),
[Meta's macOS tooling announcement](https://developers.meta.com/horizon/blog/mac-support-unity-meta-quest-horizon-developer/),
[Spatial SDK samples and prerequisites](https://github.com/meta-quest/Meta-Spatial-SDK-Samples),
[Android Studio plugin](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-android-studio-plugin/).

### Keep the test environments distinct

- **Link:** the app runs on the Windows PC and is presented through the headset.
  It provides real headset/controller tracking and rapid Unity/Unreal iteration.
  Meta explicitly warns that appearance and performance can differ from a native
  Quest build. A successful Link session does not validate the Android decoder,
  Quest GPU performance, or thermal behavior. [Link documentation, updated
  2026-04-21](https://developers.meta.com/horizon/documentation/unity/unity-link/).
- **Meta XR Simulator:** a desktop OpenXR runtime, with no Android OS image or
  hardware emulation. It can simulate controller inputs and accept forwarded
  Quest-controller data. Environment Depth simulation is documented as Windows
  only. It cannot establish native Android media playback compatibility.
  [Simulator overview, updated 2026-09-04](https://developers.meta.com/horizon/documentation/unity/xrsim-intro/).
- **Current simulator packaging:** the newer standalone Meta XR Simulator
  supersedes the deprecated Unity simulator package. Its getting-started page
  specifies Windows and ARM macOS, with Unity OpenXR 1.13.0 or later on Mac. Pin a
  compatible toolchain instead of copying older Homebrew/package setup guides.
  [Simulator setup, updated 2026-09-03](https://developers.meta.com/horizon/documentation/unity/xrsim-getting-started/).
- **Meta Spatial Simulator:** a separately named product for **2D Android apps
  only**. Its documentation explicitly excludes Spatial SDK, Unity, Unreal, and
  OpenXR apps. Do not interpret its Android Studio integration as a full Spatial
  SDK headset emulator. [Spatial Simulator, updated
  2026-09-04](https://developers.meta.com/horizon/documentation/android-apps/spatial-sim-overview/).
- **Installed Quest APK:** necessary for final media, controllers, readability,
  lifecycle, network, and performance validation. Use it early, whichever host
  and framework are selected.

If choosing only one host before choosing the framework, Windows preserves the
most iteration options, assuming the existing PC meets Link GPU requirements.
If choosing Spatial SDK, there is no strong documented reason to abandon a
productive Mac workflow. No local PC/GPU or Mac architecture inspection was
performed for this evidence brief.

## Framework comparison

### Spatial SDK: preferred first spike

Spatial SDK is Kotlin-based and supports rich Android UI panels, passthrough,
anchors, scene composition, and 3D assets. Its Android Studio plugin provides
templates and a live Data Model Inspector. The plugin also identifies unsupported
Android dependencies such as Google Mobile Services, which means an ordinary
Android library cannot automatically be assumed to work unchanged on Quest.
[Spatial SDK overview](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-explainer/),
[Android Studio plugin](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-android-studio-plugin/).

Media APIs include `VideoSurfacePanelRegistration` for direct-to-surface output
and `ReadableVideoSurfacePanelRegistration` for processing the rendered video.
Documented stereo modes include left/right and top/bottom, as well as mono
presentation. These are presentation layouts, not promises that every codec,
container, or Apple spatial asset will decode correctly. [Media playback guide,
updated 2026-04-22](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-media-playback/).

Meta's current `MediaPlayerSample` demonstrates catalog panels, flat video,
ExoPlayer-based stereoscopic 360 video, and VR/MR transitions. It is useful as a
small implementation reference; ComfyGallery does not need its YouTube WebView
path or 360 scene for ordinary media. [Media Player sample, updated
2026-05-07](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-sample-mediaplayer/).

The `Media View` showcase is closer to a complete media gallery, but its README
explicitly marks it **deprecated**, with its last update compatible with SDK
0.8.0. Use its interaction and screen ideas for reference, not as a current
dependency template. [Media View README](https://github.com/meta-quest/Meta-Spatial-SDK-Samples/blob/main/Showcases/media_view/README.md).

The sample repository's `main` resolved to commit
[`f233e2327b95f9871b75bdba867d6fdd726f07cc`](https://github.com/meta-quest/Meta-Spatial-SDK-Samples/tree/f233e2327b95f9871b75bdba867d6fdd726f07cc)
during this research. Record a tested commit and its dependency versions for the
spike instead of depending on moving `main`.

Known-issues documentation includes video-layer/mesh behavior, slower debug
builds, audio focus, and transitions between immersive activities and 2D panels.
These justify testing panel destruction, app suspend/resume, return to gallery,
and release-build playback before adopting the framework. They do not establish
that every issue remains present in every newer SDK. [Known issues, updated
2026-04-02](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-known-issues/).

### Unity: retain as the alternative

Meta recommends Unity's OpenXR provider for new projects and deprecates the
Oculus XR Plugin. The May 2026 page identifies Unity 6+, OpenXR 1.15.1, and Meta
XR SDK v74+ as its compatible/recommended family; these numbers are a dated
documentation baseline, **not a claim about the latest available release**.
Choose and pin a currently compatible Unity/SDK combination at spike time.
[XR plugin guidance](https://developers.meta.com/horizon/documentation/unity/unity-xr-plugin/).

Use Unity Input System actions for new controller code; Meta now describes
`OVRInput` as a legacy interface. Interaction SDK supplies controller ray
interactors and trigger selection. [Controller input guidance](https://developers.meta.com/horizon/documentation/unity/unity-ovrinput/),
[Controller ray interactions](https://developers.meta.com/horizon/documentation/unity/unity-isdk-create-ray-interactions/).

Do not assume Unity VideoPlayer eliminates media integration work. Unity uses
platform-native decoding, so Editor playback is not proof of Android playback.
Meta's stereo-video sample uses Android ExoPlayer on an external surface and
overlay layer for efficiency, while its desktop branch uses Unity VideoPlayer.
This demonstrates why the native media path should be tested independently of
the 3D UI framework. [Unity video compatibility](https://docs.unity3d.com/6000.0/Documentation/Manual/VideoSources-FileCompatibility.html),
[Meta stereo-video sample](https://developers.meta.com/horizon/documentation/unity/unity-sf-stereo180video/).

## User requirements and proposed scope

The user has specified Quest 3, possible design reuse from the existing XR app, optional spatial-variant playback, and controllers as the common input. The framework, exact button bindings, Home-versus-immersive launch mode, and automatic spatial-playback preference remain proposals.

Proposed first useful build:

- Connect to one gallery using its base URL and bearer token.
- Browse paginated images/videos, filter by kind/Favorite, and preserve navigation scope.
- Open one media viewer, show full-quality images, and play ordinary video with audio.
- Provide Previous/Next, Play/Pause, seek, Loop, Favorite, and an explicit close/back action.
- Support comfortable seated use with either controller and a recoverable panel position.
- Carry over filtered-sequence playback after core browsing/playback is reliable.
- Add **Play Spatial / Play in 2D** only after the selected representation is proven compatible.

Administrative tools, evaluation, workflow inspectors, generation controls, 360/180 environments, and runtime 2D-image depth generation are not implied by the requested viewer and are proposed as deferred. No production code or existing client behavior changes as part of this research.

## Reuse from the visionOS app

The reusable asset is the product contract and design language. The existing implementation is SwiftUI/RealityKit/AVFoundation, while the proposed Quest implementation uses Android/Meta APIs. Do not plan on a shared UI or player binary.

| Existing XR behavior | Quest proposal |
| --- | --- |
| Library plus a single media card | Retain the two-surface layout; make placement and resizing work with controller rays and grab handles. |
| Calm gallery, planar grid, media-first presentation | Retain hierarchy, spacing intent, thumbnail treatment, loading/error states, and uncluttered media. Adapt typography and targets to Quest viewing distance. |
| Controls below media | Retain a stable control strip; do not cover the image/video with unrelated chrome. |
| Filtered navigation and bounded neighbor preload | Port the behavior and acceptance cases, with Android cancellation/lifecycle ownership. |
| Five-second image dwell, video-end advancement, sequence temporarily takes precedence over Loop | Reuse as a proposed sequence contract rather than inventing new semantics. |
| Gaze/pinch/indirect drag | Replace with controller ray, trigger, stick, buttons, and explicit panel handles. |
| visionOS window snapping, locking, and restoration | Re-evaluate against Horizon OS activities/panels; these are not portable platform guarantees. |
| RealityKit runtime Make Spatial for images | Defer. Apple's in-memory generated scene is neither portable Quest functionality nor a backend variant. |
| XR defaults to a ready spatial video | Do not copy automatically. Quest should start with ordinary playback and an explicit optional spatial action. |

Repository sources: [XR overview](../../XR/README.md), [requirements](../../XR/product-requirements.md), [UI design](../../XR/spatial-ui-ux-design.md), [API contract](../../XR/api-and-media-contract.md), and [sequence/lifecycle handoff](../../XR/development-handoff.md).

There is a meaningful scene-model choice. Meta supports ordinary panel activities in Home and immersive OpenXR activities, including hybrid transitions and adjacent Home panels. For the closest controlled two-panel experience, prototype one passthrough scene containing Library and Viewer. If simultaneous use alongside other Horizon apps matters more, investigate Home panels/hybrid mode before locking that design. Do not equate passthrough with visionOS Shared Space, or promise persistent room anchors merely because panels can move. [Meta hybrid apps](https://developers.meta.com/horizon/documentation/spatial-sdk/hybrid-apps-overview/)

## Controller-first interaction

Meta Spatial SDK forwards controller interaction to Android panels. Its default Interaction SDK supplies pointer events and panel/object manipulation; lower-level controller data remains available for buttons and poses. Controller-first design therefore does not require Unity. [Inputs and controllers](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-inputs-controllers/), [Interaction SDK](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-isdk-overview/)

Proposed bindings, to validate on hardware:

| Input | Proposed action |
| --- | --- |
| Either controller ray + index trigger | Point, select a thumbnail, activate a button, drag a seek bar. |
| Thumbstick vertical while the Library has focus | Scroll the grid. |
| Thumbstick horizontal while the Viewer has focus | Previous/Next, with a dead zone and repeat debounce. |
| Grip while targeting a panel handle | Reposition the panel; resize through an explicit handle or control. |
| B/Y | App back/close, subject to platform-reserved actions and focus rules. |
| Visible player buttons | Play/Pause, Loop, Favorite, seek, optional Spatial/2D; every essential action stays discoverable without memorized shortcuts. |

Use hover/pressed feedback, adequate target spacing, one active pointer/focus policy, and optional brief haptics. Prevent a button press from simultaneously activating a panel and a global shortcut. A gallery does not need teleportation or snap turning: configure scene locomotion deliberately so sample defaults do not conflict with navigation. Do not hijack the Meta system button. Keep hand tracking optional and do not require gaze targeting. These are product proposals, not Meta-mandated mappings.

## Optional spatial playback: evidence and limits

### What the current backend actually stores

The existing `spatial_video` role means a validated Apple spatial MV-HEVC file, not an arbitrary SBS video. The validator checks an MP4/QuickTime-family container, HEVC, Apple spatial metadata, and decoding of both views. The import route currently accepts only that role, and storage permits at most one active variant per media/role. Ordinary `playback_url` retains its original/proxy meaning.

Sources: [validator](../../packages/py/core/src/comfy_gallery_core/media/spatial_video.py), [variant import route](../../apps/api/src/comfy_gallery_api/routes/variants.py), [variant model/index](../../packages/py/core/src/comfy_gallery_core/db/models.py), [variant response](../../apps/api/src/comfy_gallery_api/media_schemas.py), and [ADR-0011](../decisions/0011-imported-media-variants.md).

### What current Quest documentation establishes

Meta's streaming-media guidance, updated August 28, 2026, recommends MV-HEVC with AV1 side-by-side fallback for rectilinear 3D content and advises checking device codec capabilities. Consequently, a blanket assertion that Quest cannot play MV-HEVC is not justified by current primary sources. However, that guidance alone does not demonstrate that the stock Spatial SDK/ExoPlayer path can render both eyes of our particular Apple MOV files on the intended Quest 3 OS version. [Meta media requirements](https://developers.meta.com/horizon/documentation/android-apps/media-requirements/)

Meta's public Spatial Video sample concretely demonstrates ExoPlayer rendering side-by-side stereo to a panel surface with `StereoMode.LeftRight`. That is a documented fallback path, not proof of direct Apple MV-HEVC compatibility. [Spatial Video sample](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-sample-video/)

A player vendor also lists MV-HEVC and MOV support for its Spatial SDK integration. Treat that as an alternative to evaluate if necessary, not verified performance, compatibility, availability, or a dependency selected for ComfyGallery. [HISPlayer's own compatibility documentation](https://hisplayer.github.io/MetaSpatial-SDK/)

Do not substitute Google's Android XR `SurfaceEntity` documentation for Quest/Horizon OS support. It requires an Android XR device with the relevant decoder and is a different platform API. [Android XR spatial video](https://developer.android.com/develop/xr/jetpack-xr-sdk/add-spatial-video)

### Proposed behavior

Start ordinary playback immediately through `playback_url`. Offer spatial playback only when all of the following hold:

1. The user opts into spatial playback.
2. The backend reports availability and supplies an active ready representation.
3. The chosen player/runtime supports that representation on the actual device.
4. Loading, stereo presentation, and audio succeed.

On unsupported format or playback failure, keep the logical media selected, return to ordinary playback, and show a brief explanation. Preserve playback position where practical. A local unsupported result must not clear server availability, Favorite, or the shared playback preference. Never treat a successfully decoded base-eye image as proof of stereoscopic playback.

For the first optional implementation, **Play Spatial** and **Play in 2D** should be session-only choices. If automatic spatial defaults are later wanted, define an explicit policy using device capability and the shared `prefer_spatial_playback` field. The current XR app intentionally ignores that preference for video defaults, so copying its selection logic would silently decide a product question that the user has not settled. [Current XR source-selection contract](../../XR/api-and-media-contract.md#playback)

If direct MV-HEVC works, reuse existing `content_url` delivery with no format migration. If it does not, first keep the app 2D and decide whether the optional feature warrants an SBS fallback. Publishing SBS would require an explicit backend contract/ADR change: separate representation identity, stereo layout and eye order, codec/profile/container facts, validation, capability selection, and coexistence with the Apple variant. Uploading SBS under today's `spatial_video` role is invalid and must not replace the Vision Pro file. Reusing the external converter's SBS output is a promising follow-up, but its durable availability and publication support were not verified here.

Conversion remains externally executed. Preserve the current orchestration boundary: clients call ComfyGallery; MSS performs GPU work; ComfyGallery validates and serves completed variants. [ADR-0013](../decisions/0013-orchestrate-external-spatial-conversion.md), [ADR-0014](../decisions/0014-event-driven-mss-orchestration.md)

## Proposed client architecture and integration

Use a future `Quest/` boundary, separate from `XR/` and `mobile/`. This is a proposed directory, not a scaffold created by this task.

Keep three practical layers:

1. **Gallery data:** server profile, authentication, narrow DTOs, filters/pages, detail/navigation, Favorite, cache and cancellation.
2. **Quest presentation:** Compose Library/controls, panel placement, controller actions, focus and lifecycle.
3. **Media session:** one active player, ordinary image/video presentation, representation selection, optional stereo adapter, sequence timing and bounded prefetch.

Reuse the API and its invariants, including media IDs, server-supplied relative URLs, same-origin bearer authentication, independent Favorite/preference/availability, and ordinary playback fallback. Reuse the XR pagination lesson: both `ready` and `ready_with_warnings` are playable, and local filtering must preserve raw server offsets rather than skipping or stranding pages. [XR integration contract](../../XR/api-and-media-contract.md), [repository paging](../../XR/ComfyGalleryXR/Core/Media/GalleryRepository.swift)

Unlike the XR implementation's initial full-download approach, Media3 can use explicit HTTP request headers. Prototype authenticated streaming and seeking before deciding the final cache policy. Constrain credentials to the configured origin, including redirects; never put the token in media URLs. Provide bounded disk caching and release decoder/surface ownership on close, selection change, activity pause, and headset removal. [Media3 HTTP data-source factory](https://developer.android.com/reference/androidx/media3/datasource/DefaultHttpDataSource.Factory)

Retain ordinary playback without a running converter or Windows PC. After installation, the standalone app runs on the Quest and reaches the gallery server; a development host is not part of its runtime architecture. A machine hosting the gallery or executing requested conversions still needs to be available for that role.

## Small validation plan before implementation commitment

**Core gate:** Build a current Meta sample and deploy it to Quest 3. Replace its catalog with a narrow authenticated Gallery client. Demonstrate a paginated thumbnail grid, one selected image, one ordinary video with audio, seeking over authenticated byte ranges, and controller-only navigation. Check clarity, comfort, focus, and close/reopen behavior in the headset.

**Independent optional gate:** Load one known-good Gallery MV-HEVC variant through the intended shipping player. Record Quest OS, SDK/player versions, file codec/container/profile, both-eye output, eye order, audio, seek, pause/resume, repeated Loop, ordinary/spatial switching, and sustained playback. Test representative larger files before promising maximum resolution or smoothness. Compare a known SBS reference if needed.

Core failure is a reason to revisit the stack. Optional stereo failure is a reason to ship ordinary media and defer that feature. Simulator or Link success is not standalone decoder, performance, or comfort evidence.

The next design decision is whether this client primarily lives alongside other Horizon apps in Home panels, or opens a focused passthrough gallery scene. Both can share much of the same Kotlin data and Compose UI code. The recommendation is to validate the focused two-panel scene first because it directly exercises the XR design reuse and controller ergonomics requested here.

## Coordination and scope

Read the body and recent comments of [spatial tracker #2](https://github.com/blkot/ProjectComfyGallery/issues/2). It is closed and its original Apple-only scope excluded Quest/Android. The user's current request authorizes new Quest research; it does not retroactively change that completed contract. Implementation should receive its own Quest scope and any necessary backend-format decision before modifying shared semantics.

The source review found existing unrelated documentation edits. They remain preserved. This research introduces no new API, dependencies, application implementation, or deployment.
