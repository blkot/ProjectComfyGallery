# Spatial UI/UX Design

**Status:** Design handoff for Apple Vision Pro MVP

**Design character:** Calm gallery, media-first, native glass and spatial behavior

## Experience principles

1. **Place, do not surround.** Let the user position a small number of useful
   windows. Do not fill the room with independent tiles.
2. **Media remains the hero.** Navigation and conversion controls live in ornaments
   or window chrome, not over important pixels.
3. **Gaze identifies; pinch commits.** Hover confirms targetability, but nothing opens
   merely because the user looks at it.
4. **Movement is optional.** The entire experience works seated with hands resting.
5. **Depth is a feature, not decoration.** Grid and text stay planar. Generated depth
   appears only inside the selected image.
6. **The system owns the room.** Use standard window bars, resizing, snapping,
   locking, restoration, recentering, and player controls.

## Scene inventory

```text
Connect (transient)
    └─ opens Library after successful authentication

Library (primary, restorable)
    ├─ adaptive media grid
    ├─ compact filter/search ornament
    └─ opens or updates Media card

Media card (single auxiliary, restorable)
    ├─ image / generated spatial scene / video
    └─ navigation + Make Spatial ornament
```

No scene is head-locked. No Full Space opens in MVP.

## Connect scene

- Standard glass window, compact content-sized layout.
- Restoration disabled.
- Fields:
  - Gallery URL
  - API token
- Actions:
  - Connect
  - Paste
  - Cancel when an existing profile remains usable
- States:
  - Checking server
  - Server found, authenticating
  - Connected
  - Cannot reach server
  - Token rejected

The token field uses secure text entry. Never show its complete value after
connection.

Plain HTTP displays a one-time trusted-LAN warning. It does not silently rewrite the
URL or block the user's private deployment.

## Library window

### Window behavior

- Default starting size: approximately 1,180×760 points.
- Minimum useful size: approximately 720×520 points.
- Resizable through system controls.
- Scene restoration enabled.
- Standard glass background.
- The app may suggest initial center placement; the user/system decides.

### Header and ornament

Inside the window:

- title: **Gallery**;
- item count/loading state;
- Refresh.

Use a restrained top or bottom ornament for:

- All / Images / Videos;
- Hide Trash / Include Trash;
- sort menu, default Newest;
- connection status.

Do not create floating custom 3D text or controls.

### Grid

- `ScrollView` + `LazyVGrid`.
- Adaptive columns; cards generally 180–240 points wide depending on window size.
- Default 2:3 frame.
- 16 points or more between visual cards; ensure combined eye target areas remain at
  least 60 points.
- Aspect-fill preview clipped to a rounded rectangle.
- Video glyph in one corner.
- Optional subtle Trash treatment.
- No filename, UUID, hash, dimensions, prompt, or model/workflow text.
- Use a system hover effect: slight lift/brightness, not a large scale jump.
- Air tap opens the Media card.

Skeleton cells should retain the target aspect ratio. Paging appends rows without
shifting already visible cells.

### Grid loading states

- Initial: a modest set of aspect-ratio skeletons.
- Paging: spinner in a final row, existing media remains interactive.
- Page failure: inline Retry row.
- Empty: “No media matched this view.”
- Offline with cached results: nonmodal offline ornament and cached cards.
- Preview failure: neutral image/video placeholder with Retry.

## Media card

### Window behavior

- One `Window` scene, not an unbounded `WindowGroup`.
- Initial placement suggested to the trailing side of Library when space permits.
- Default size: approximately 900×700 points.
- Minimum size: approximately 480×360 points.
- Resizable and restorable.
- Standard window bar remains available for movement, snapping, locking, and close.
- A dark neutral backing exists only behind letterboxed media, not as a large opaque
  environment.

The card remains usable after Library closes. Reopening Library does not create a
second card.

### Image state

- Contain the image inside the available card.
- Preserve aspect ratio.
- Avoid cropping by default.
- Use display-sized decoding for ordinary 2D mode.
- If zoom is included, make it an explicit double tap/zoom gesture and ensure it
  does not conflict with horizontal navigation; zoom can be deferred from MVP if
  interaction testing is ambiguous.

### Video state

- Show poster/loading state immediately.
- Present `AVPlayerViewController`.
- Auto-play when ready and active.
- Use system playback controls.
- Pause when the scene becomes inactive or navigation begins.
- Do not auto-play neighbor videos during prefetch.
- Do not place custom buttons over the player surface.

### Bottom ornament

```text
[ Previous ]   18 / 503   [ Next ]     [ Make Spatial ]
```

- Previous/Next are always present and disable at scope boundaries.
- Position updates from the navigation response.
- Make Spatial appears only for compatible image media.
- During generation it becomes **Making Spatial…** with progress activity and Cancel.
- After generation it becomes **Disable Spatial**.
- A Favorite control appears for all media. Spatial images remain favorited until
  Disable Spatial is selected.
- Video cards omit spatial conversion.

Keep ornament width no wider than the card and use borderless system buttons on its
glass background.

## Indirect drag navigation

The user's “pinch and drag” is implemented as a normal SwiftUI horizontal
`DragGesture`: look at the card, pinch to select, then move left or right.

### Recognition

- Begin only within the media navigation region.
- Ignore primarily vertical motion.
- Do not attach navigation to AVKit transport controls.
- A practical starting threshold is the smaller of 120 points or 20% of card width.
- A high predicted end velocity may commit slightly before the distance threshold.
- Below threshold, spring/fade back to the current item.
- At first/last item, apply restrained resistance and remain in place.

Exact thresholds must be tuned on physical hardware.

### Animation

During drag:

- current media moves slightly with the gesture;
- destination neighbor may appear subtly from the relevant side when already
  prepared;
- no room-scale movement, rotation, or exaggerated depth occurs.

On commit:

- pause current video;
- settle the new media;
- update position and accessibility focus only after explicit action;
- auto-play if the new media is video.

With Reduce Motion, use a short fade and minimal translation.

### Alternatives

Previous and Next buttons are normative. Keyboard arrows, trackpad, Switch Control,
VoiceOver, and Dwell Control must be able to navigate without the drag gesture.

## Neighbor preload experience

The UI represents four preparation states:

- **Ready:** destination media can appear immediately.
- **Preview ready:** transition to preview/poster, then upgrade to full media.
- **Loading:** show contained activity without removing navigation chrome.
- **Failed:** stay on current media or show destination error with Retry.

Prefetch priority:

1. Current media.
2. Next media.
3. Previous media.
4. Near-visible grid previews.

When direction becomes clear during a drag, boost that neighbor and deprioritize the
opposite neighbor. Never pre-generate spatial depth.

## Paging and continuous order

- Library uses page size 48 by default.
- Begin fetching the next page roughly two grid rows before the end.
- Deduplicate appended items by media UUID.
- Preserve raw offset advancement even if a page contains duplicate IDs.
- Avoid automatic refresh while a drag is active.

Viewer navigation is not limited to locally loaded pages. It calls the backend
navigation endpoint with the current filter/sort to obtain previous/next media IDs.
When a returned neighbor is absent from the local page cache, fetch its narrow media
detail and prepare it directly.

New imports can change live positions. Keep the current media ID stable and accept an
updated total/position after the next explicit navigation request; never jump the
visible item automatically.

## Make Spatial UX

### Eligibility

Use known dimensions for a fast preflight:

- image only;
- shortest side at least 320 pixels;
- largest side at most 16,384 pixels;
- aspect ratio between 1:3 and 3:1.

Passing the preflight does not guarantee generation; invalid/unsupported source data
may still fail.

### First-use explanation

On first use:

> Make Spatial generates depth on this Vision Pro. The result may contain artifacts.
> Your original gallery image is never changed.

Actions:

- Make Spatial
- Not Now

Do not repeat the explanation unless requested from Help.

### Generation

- Keep the original 2D image visible.
- Use RealityKit's generation transition when available.
- Show a small cancelable status in the ornament.
- Cancel when the user navigates, closes the card, disconnects, or the scene becomes
  inactive for a sustained period.
- On failure, show a short nonmodal message and remain in 2D.

### Spatial presentation

- Use `.spatial3D`, not `.spatial3DImmersive`, in MVP.
- Fit the `ImagePresentationComponent` to the resizable RealityView bounds.
- Avoid placing text or controls at competing depths.
- Keep Disable Spatial instantly available.
- Keep up to five generated images in a session-only LRU. When navigation returns
  to one of them, restore its spatial presentation without regenerating.
- A persisted spatial preference with no session entry (such as after relaunch)
  requests automatic regeneration after the ordinary image becomes available.

## Materials, typography, and color

- Keep system glass for windows and ornaments.
- Use semantic materials and vibrancy instead of hard-coded translucent colors.
- Use SF Pro and Dynamic Type.
- Prefer 2D text.
- Use SF Symbols by name.
- Media backing may use a near-black semantic surface for accurate contrast, limited
  to the content rectangle.
- Test bright and dark physical environments; visionOS glass adapts rather than
  offering a conventional Dark Mode toggle.

## Accessibility and comfort

- Use standard controls and hover effects.
- Provide at least a 60-point combined eye-target area for custom controls.
- Use labels in addition to symbols where action is not obvious.
- Do not change content on gaze alone.
- Do not require arms to remain raised.
- Avoid multiple simultaneous depth planes.
- Never anchor controls to the user's head or hands.
- Keep all important controls near the active card.
- Support VoiceOver descriptions such as “Image, item 18 of 503” without filename or
  hidden metadata.
- Announce loading failures and spatial-generation completion politely.
- Respect Reduce Motion and accessibility pointer alternatives.

## UX validation

- Seated use with hands in lap.
- Standing use with Library snapped to a wall.
- Library near/far dynamic scale.
- Small and large Media card resizing.
- Bright room, dark room, and system Environment.
- Eye targeting with dense portrait grid.
- Dwell Control and VoiceOver navigation.
- Video timeline interaction without accidental gallery navigation.
- Repeated 50-item navigation without arm/eye fatigue.
- Spatial conversion success, cancellation, error, and 2D fallback.
- Closing/reopening scenes and full device restart restoration.
