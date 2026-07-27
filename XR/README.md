# Project Comfy Gallery XR

**Status:** Research-backed handoff specification

**Research date:** 2026-07-27

**Target:** Apple Vision Pro, visionOS 26 or later

**Recommended stack:** Swift 6, SwiftUI, RealityKit, AVKit, URLSession, SwiftData

## Purpose

Project Comfy Gallery XR is a native spatial media viewer for the existing
self-hosted gallery. Its first MVP is intentionally focused:

1. Connect to one gallery using its LAN URL and a bearer API token.
2. Browse managed images and videos in a spatially placed, resizable grid window.
3. Air tap a media item to open one resizable media card.
4. Auto-play videos and present images at high quality.
5. Navigate with explicit controls or an indirect look-pinch-drag gesture.
6. Preload neighboring media and cross pagination boundaries without visible stalls.
7. Optionally convert a compatible 2D image into an on-device spatial scene.

Evaluation, workflow metadata, model information, imports, administration, and
analytics are outside the first XR milestone.

## Platform decision

Build a native visionOS application. SwiftUI supplies the window and spatial scene
model, RealityKit supplies image/spatial-scene presentation, and AVKit supplies the
system video player. A web wrapper cannot provide the same spatial window
restoration, hover behavior, RealityKit spatial-scene generation, or native media
presentation.

The minimum target is visionOS 26 because Apple introduced
`ImagePresentationComponent.Spatial3DImage` for converting 2D images into spatial
scenes in that release. Development and ordinary UI testing can use Simulator, but
spatial-scene generation must be verified on physical Apple Vision Pro hardware.

## What “spatially anchored” means in the MVP

The MVP runs in Shared Space and uses system-managed windows:

- **Library window:** the primary glass window containing the media grid.
- **Media card:** one auxiliary, resizable window containing the selected image or
  video.

People place these windows in their environment using the standard window bar. On
visionOS 26, system surface snapping, locking, and scene restoration can keep
supported windows attached to a wall or other appropriate surface across sessions.
The app preserves scene identity and content state; it does not force a physical
position.

This is preferable to a custom `ImmersiveSpace` for the first milestone:

- it supports multitasking and passthrough;
- it requires no hand-tracking or world-sensing permission;
- it uses standard, comfortable indirect input;
- the system manages placement, scale, snapping, and recentering; and
- the user remains in control of where content lives.

ARKit `WorldAnchor` placement is a different feature. It requires a Full Space for
ARKit data access and is deferred until the product has a use case that cannot be
served by persistent windows.

## 2D-to-3D conclusion

Apple now provides a supported third-party path:

- Load a local image into `ImagePresentationComponent.Spatial3DImage`.
- Present it through `ImagePresentationComponent` in a `RealityView`.
- Call `generate()` to create an in-memory spatial scene.
- Select `.spatial3D` for windowed depth and motion parallax.
- Keep `.mono` as an explicit fallback.

Generation takes a few seconds, does not work in Simulator, and can create visual
artifacts. It is therefore an explicit **Make Spatial** action, not an automatic
operation applied to every grid item or neighbor.

See [research findings](research-findings.md) for constraints and primary Apple
sources.

## Handoff documents

Read in this order:

1. [Research findings](research-findings.md)
2. [Product requirements](product-requirements.md)
3. [Spatial UI/UX design](spatial-ui-ux-design.md)
4. [API and media contract](api-and-media-contract.md)
5. [Development handoff](development-handoff.md)

The current server implementation remains authoritative:

- [`apps/api/src/comfy_gallery_api/routes/media.py`](../apps/api/src/comfy_gallery_api/routes/media.py)
- [`apps/api/src/comfy_gallery_api/media_schemas.py`](../apps/api/src/comfy_gallery_api/media_schemas.py)
- [`apps/api/src/comfy_gallery_api/routes/auth.py`](../apps/api/src/comfy_gallery_api/routes/auth.py)
- [`apps/api/src/comfy_gallery_api/dependencies.py`](../apps/api/src/comfy_gallery_api/dependencies.py)

## Locked MVP decisions

- Native visionOS app targeting stable visionOS 26 APIs.
- Shared Space, not Full Space, for the first milestone.
- One primary Library window and at most one Media card.
- Both scenes are movable, resizable, restorable, and eligible for system surface
  snapping/locking.
- Simple base URL plus pasted API token onboarding.
- Token stored only in Keychain.
- Visual media browsing only; no metadata inspector.
- Default grid cell aspect ratio is 2:3.
- Air tap opens or updates the single Media card.
- Video auto-plays only after it becomes the active card item.
- Navigation uses buttons and a standard indirect horizontal drag.
- No custom hand tracking or private gaze data.
- Current and immediate neighbors are preloaded within strict memory/disk budgets.
- Library pagination is incremental and cancelable.
- 2D-to-spatial conversion is on demand, image-only, and reversible to 2D.
- Spatial-scene generation never modifies or uploads a replacement for the gallery
  original.
- No immersive environment, spatial audio design, SharePlay, or multi-window wall of
  media in MVP.

## Definition of the first useful build

The first useful build can:

- connect and authenticate against the existing NAS backend;
- restore the Library window where the user placed it;
- page a large mixed image/video library smoothly;
- open one resizable Media card beside the Library;
- contain images and play videos with system controls;
- auto-play the newly selected video and stop the previous one;
- navigate through page boundaries with buttons and look-pinch-drag;
- show the current position and recover from deleted/unavailable media;
- prefetch neighbor thumbnails/media without unbounded memory or network use;
- generate and display a spatial scene from a compatible 2D image on a physical
  Vision Pro;
- return to the original 2D image after conversion; and
- pass the accessibility, network-loss, scene-restoration, and device tests in the
  development handoff.

## Implemented app

The standalone native app lives entirely in this directory:

```text
XR/
├─ ComfyGalleryXR.xcodeproj
├─ ComfyGalleryXR/
├─ ComfyGalleryXRTests/
├─ ComfyGalleryXRUITests/
└─ project.yml
```

Generate and build it from `XR/`:

```sh
xcodegen generate
xcodebuild \
  -project ComfyGalleryXR.xcodeproj \
  -scheme ComfyGalleryXR \
  -destination 'generic/platform=visionOS Simulator' \
  build
```

The generated Xcode project is kept in this directory so Xcode can open it directly.
`project.yml` remains the source of truth for target and build settings. Simulator
can verify connection, library, viewer, gesture, playback, restoration, and
accessibility behavior. **Make Spatial** intentionally reports unavailable in
Simulator; validate generation, surface snapping/locking, comfort, and final AVKit
behavior on physical Apple Vision Pro hardware.
