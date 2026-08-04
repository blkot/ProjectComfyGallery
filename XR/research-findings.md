# visionOS Research Findings

**Scope:** Apple Vision Pro spatial media gallery

**Research date:** 2026-07-27

**Source policy:** Primary Apple documentation and Apple Developer videos

## Executive findings

1. **A native windowed app is the correct first architecture.** Apple recommends
   starting with familiar windows and adding volumes or immersive spaces when depth
   is central to the experience. A grid and a media viewer are UI-centric and fit
   standard windows well.
2. **System windows satisfy the practical anchoring requirement.** People control
   window placement. visionOS 26 supports restoration plus surface snapping and
   locking so supported scenes can remain attached to their physical environment.
3. **Apple exposes 2D-to-spatial conversion to third-party apps.**
   `ImagePresentationComponent.Spatial3DImage` can generate textured 3D geometry from
   an ordinary 2D image and present motion parallax in a RealityKit scene.
4. **The conversion requires visionOS 26 and physical hardware.** Generation is not
   available in visionOS Simulator and normally takes a few seconds.
5. **The result is a spatial scene, not a true captured stereo photo.** Apple
   distinguishes generated geometry from spatial photos, which contain separate
   left/right images and capture metadata.
6. **Use standard indirect gestures.** Look plus pinch, tap, and drag are already
   exposed through SwiftUI gestures. Custom hand tracking would add fatigue,
   permissions, and Full Space requirements with no MVP benefit.
7. **Use the system AVKit player for video.** Apple recommends
   `AVPlayerViewController` for windowed visionOS playback.

## Scene and anchoring model

### Standard windows

Apple describes a standard window as the best choice for familiar, UI-centric
interfaces. Windows provide system controls for relocation and resizing and receive
dynamic scale so content remains legible at different distances.

For this app:

- the Library is a primary window;
- the Media card is an auxiliary window;
- both remain in Shared Space;
- the user chooses their physical placement; and
- the system performs final placement and movement behavior.

An app can suggest an initial relative placement for a secondary scene through
`defaultWindowPlacement`, but it cannot treat the room as a pixel canvas or assume
its preferred placement will always be used.

Primary sources:

- [Windows — Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/windows)
- [Creating your first visionOS app](https://developer.apple.com/documentation/visionOS/creating-your-first-visionos-app)
- [`defaultWindowPlacement(_:)`](https://developer.apple.com/documentation/swiftui/scene/defaultwindowplacement%28_%3A%29)

### Surface snapping, locking, and restoration

visionOS 26 lets people snap windows near suitable surfaces and lock supported,
restorable content in place. Locked content can persist through room changes, device
removal, recentering, and relaunch.

MVP implication:

- use stable scene IDs;
- leave scene restoration enabled for Library and Media card;
- persist the selected media ID and active gallery view;
- do not restore onboarding;
- let the system expose snapping and locking; and
- do not request detailed surface classification unless the UI actually adapts to
  wall/table/floor context.

Primary source:

- [Adopting best practices for persistent UI](https://developer.apple.com/documentation/visionOS/adopting-best-practices-for-scene-restoration)

### Why not ARKit world anchors in MVP

`WorldAnchor` represents a fixed real-world location and ARKit can persist its UUID
and transform. However, ARKit data is available to a visionOS app only while it
presents a Full Space. A Full Space hides other apps and expands privacy/lifecycle
scope.

The grid and card already gain user-controlled spatial placement, snapping, and
restoration from standard scenes. Custom world anchors provide no necessary MVP
behavior.

Primary sources:

- [`WorldAnchor`](https://developer.apple.com/documentation/arkit/worldanchor)
- [Setting up access to ARKit data](https://developer.apple.com/documentation/visionos/setting-up-access-to-arkit-data/)

## 2D image to spatial scene

### Available API

RealityKit's `ImagePresentationComponent` supports:

- ordinary 2D images;
- captured spatial photos; and
- generated spatial scenes.

To generate a spatial scene:

1. Download the authenticated gallery original to a local file.
2. Create `ImagePresentationComponent.Spatial3DImage` from the local URL or a
   `CGImageSource`.
3. Create `ImagePresentationComponent(spatial3DImage:)`.
4. Attach the component to an otherwise empty RealityKit entity.
5. Set `desiredViewingMode` to `.spatial3D`.
6. Call `generate()` asynchronously.
7. Keep `.mono` available as the reversible 2D fallback.

The generated scene uses computational depth to create multiple viewpoints and
motion parallax as the viewer moves their head.

Primary sources:

- [`ImagePresentationComponent`](https://developer.apple.com/documentation/realitykit/imagepresentationcomponent)
- [`ImagePresentationComponent.Spatial3DImage`](https://developer.apple.com/documentation/realitykit/imagepresentationcomponent/spatial3dimage)
- [Presenting images in RealityKit](https://developer.apple.com/documentation/realitykit/presenting-images-in-realitykit)
- [What’s new in RealityKit — WWDC25](https://developer.apple.com/videos/play/wwdc2025/287/)

### Input and runtime constraints

Apple documents these `generate()` constraints:

- shortest image side: at least 320 pixels;
- largest image side: at most 16,384 pixels;
- aspect ratio: between 1:3 and 3:1;
- valid local image data is required;
- generation can take a few seconds;
- cancellation is supported through enclosing Swift task cancellation;
- calling `generate()` after the same object already generated throws; and
- generation and spatial-scene viewing do not work in Simulator.

Source:

- [`Spatial3DImage.generate()`](https://developer.apple.com/documentation/realitykit/imagepresentationcomponent/spatial3dimage/generate%28%29)

### Quality and product implications

Apple notes that generated spatial scenes can contain visual artifacts. AI-generated
images may be especially challenging because depth cues, anatomy, reflections, and
occlusion can already be ambiguous.

Therefore:

- conversion is explicit, not automatic;
- the 2D original remains immediately accessible;
- a failure never prevents ordinary viewing;
- no generated representation replaces the managed original;
- neighbor prefetch downloads source bytes but never pre-generates depth;
- generation cancels when the user navigates away; and
- the app may keep a small in-memory generated-scene cache for the active session,
  but the specification does not assume an exportable disk representation.

### Spatial scene versus spatial photo

| Capability | Spatial scene | Spatial photo |
|---|---|---|
| Source | One ordinary image | Captured left/right stereo pair |
| Depth basis | Generated geometry/computational depth | Binocular disparity |
| Relevant modes | `.spatial3D`, `.spatial3DImmersive` | `.spatialStereo`, `.spatialStereoImmersive` |
| MVP use | Convert existing gallery images | Future, after gallery supports spatial HEIC |

The current gallery MVP ingests PNG, JPEG, WebP, MP4, and WebM, not spatial HEIC.
The XR MVP therefore focuses on generated spatial scenes from existing 2D images.

## Video presentation

Apple recommends `AVPlayerViewController` for a windowed visionOS playback interface.
It supplies standard transport controls, platform integration, and familiar behavior.
The system player supports standard 2D and spatial/3D video without a custom stereo
renderer. An Apple spatial video uses MV-HEVC in an MPEG-4 or QuickTime-family
container plus spatial metadata; the metadata opts playback into Vision Pro's
spatial presentation and comfort treatments.

The Destination Video sample demonstrates a native media library and player; its
immersive environment is useful reference material but outside this MVP.

The gallery's media endpoints require bearer authentication. A plain player URL
cannot safely contain the token. The backend therefore exposes the active spatial
variant as an authenticated `content_url` and leaves ordinary `playback_url`
unchanged. The reliable first implementation is:

1. Select the ready spatial variant only when both `prefer_spatial_playback` and
   `spatial_available` are true; otherwise select ordinary `playback_url`.
2. Download the selected path through authenticated `URLSession`.
3. Write it atomically into a bounded media cache keyed by representation and
   variant UUID.
4. Preserve `video/quicktime` as a local `.mov` file.
5. Create `AVPlayerItem` from the local file URL.
6. Present it in `AVPlayerViewController` with monoscopic-only mode disabled.
7. Configure `experienceController.allowedExperiences = .recommended()`.
8. For spatial-video playback, transition the experience controller from
   `.embedded` to `.expanded`, wait for `.completed`, and only then call `play()`.
9. Reconcile back to `.embedded` before ordinary 2D playback and when the player is
   dismantled.
10. Keep the `AVPlayer` and `AVPlayerViewController` alive across ordinary/spatial
    source changes; replace only the current item so AVKit owns the visible
    embedded/expanded transition and Loop survives.
11. Remove the poster layer after the AVKit surface exists rather than stacking a
    differently sized video surface over the preview.

Setting `requiresMonoscopicViewingMode = false` is necessary but does not itself
request spatial presentation. The physical-device regression in issue #8 confirmed
that a valid spatial MV-HEVC asset remains monoscopic in the embedded player until
the AVKit experience transition occurs.

Primary sources:

- [Adopting the system player interface in visionOS](https://developer.apple.com/documentation/avkit/adopting-the-system-player-interface-in-visionos)
- [Playing immersive media with AVKit](https://developer.apple.com/documentation/avkit/playing-immersive-media-with-avkit)
- [Support immersive video playback in visionOS apps — WWDC25](https://developer.apple.com/videos/play/wwdc2025/296/)
- [Converting side-by-side 3D video to multiview HEVC and spatial video](https://developer.apple.com/documentation/avfoundation/converting-side-by-side-3d-video-to-multiview-hevc-and-spatial-video)
- [Destination Video](https://developer.apple.com/documentation/visionos/destination-video)
- [`AVPlayerItem`](https://developer.apple.com/documentation/avfoundation/avplayeritem)

The deployed backend also supports byte ranges. If physical-device measurements make
full download unacceptable, a follow-up can implement an authenticated AVFoundation
resource-loading path against that endpoint. Do not put a bearer token in a URL or
depend on undocumented asset-header options.

## Spatial interaction findings

### Eyes and indirect gestures

The system uses gaze privately as a targeting mechanism and supplies hover effects.
The app receives action intent, not raw gaze coordinates. Use:

- air tap to activate a grid item;
- standard `DragGesture` for look-pinch-drag navigation;
- system buttons as an equivalent alternative; and
- system hover effects rather than custom gaze animation.

Apple recommends a minimum 60-point eye-target area when control size and spacing
are considered together. Standard components already account for this.

Primary sources:

- [Design for spatial input — WWDC23](https://developer.apple.com/videos/play/wwdc2023/10073/)
- [Gestures — Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/gestures)

### Comfort and layout

Apple guidance that directly affects this app:

- keep core content within a comfortable field of view;
- prefer horizontal over tall vertical arrangements;
- avoid many simultaneous windows;
- use depth only where it clarifies hierarchy;
- avoid depth on text;
- minimize repetitive/large gestures;
- keep interactive centers generously separated;
- offer button alternatives to gestures;
- avoid head-locked content; and
- rely on the Digital Crown for user-initiated recentering.

Primary sources:

- [Spatial layout — Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/spatial-layout/)
- [Accessibility — Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- [Designing for visionOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-visionos)

### Materials and ornaments

visionOS windows use adaptive glass to retain environmental context. Controls and
navigation should use system materials and vibrancy. An ornament is appropriate for
frequent viewer actions because it stays attached to the window without covering
media.

Use one restrained bottom ornament for:

- Previous;
- position;
- Next; and
- Make Spatial / Disable Spatial when applicable.

Primary sources:

- [Materials — Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/materials)
- [Ornaments — Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/ornaments)

## Version strategy

- **Deployment target:** visionOS 26.0.
- **API policy:** use stable visionOS 26 APIs for the MVP.
- **visionOS 27:** test compatibility, but do not make the first build depend on beta
  APIs.
- **Simulator:** use for grid, windows, network, gestures, and layout.
- **Physical Vision Pro:** required for spatial-scene generation, comfort, gaze/hover,
  window placement, surface locking, and final video validation.
