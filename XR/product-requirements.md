# XR Product Requirements

**Status:** Proposed first-MVP scope

**Platform:** Apple Vision Pro, visionOS 26+

## Product statement

Project Comfy Gallery XR turns the existing self-hosted media library into a calm
spatial viewing experience. The user places a visual Library window in their room,
opens one resizable media card, and moves continuously through images and videos
without returning to the grid. Compatible 2D images can become on-device spatial
scenes without altering the backend original.

## Goals

- Make a large mixed gallery comfortable to browse in Shared Space.
- Let the user place, resize, snap, lock, and restore the app's windows naturally.
- Make opening and navigating media feel immediate.
- Auto-play active videos with standard playback controls.
- Cross pagination boundaries without a visible mode switch.
- Bound memory, disk, decoding, and network activity.
- Provide a supported, reversible 2D-to-spatial-scene experience.
- Preserve privacy of the LAN URL and bearer token.

## Non-goals

- Blind review or evaluation.
- Metadata, prompt, workflow, checkpoint, or LoRA presentation.
- Imports, scans, node/model registry, analytics, or operations.
- Editing or deleting media.
- Multiple simultaneous media cards.
- A free-form wall containing hundreds of independent media entities.
- Full Space, custom world anchors, room mesh, plane detection, or hand tracking.
- Custom hand gestures or raw gaze tracking.
- Immersive video, 180°/360° projection, Apple Immersive Video, or custom environments.
- Spatial photo ingestion or server-side 3D asset generation.
- SharePlay or nearby multi-user viewing.
- Full offline library synchronization.

## Assumptions

- One person uses one gallery server.
- The Vision Pro and NAS are normally on the same trusted LAN.
- Most files are several megabytes.
- The backend remains available at a user-configured HTTP or HTTPS URL.
- Existing bearer API tokens are sufficient for V1.
- Media identities are UUIDs; filenames are irrelevant.
- The primary sort is file creation time descending.

## User journeys

### Connect

1. Launch the transient Connect window.
2. Enter the gallery base URL and paste a device API token.
3. Validate `/health/live`, then `/api/v1/auth/session`.
4. Store the normalized base URL and Keychain token.
5. Open the Library window and dismiss Connect.

### Browse

1. The restored Library window loads the newest page.
2. Scroll an adaptive 2:3 grid.
3. Optionally filter All / Images / Videos and include/hide Trash.
4. Near the page boundary, the next page loads without replacing visible content.
5. Hover identifies an actionable card; air tap opens the Media card.

### View and navigate

1. The Media card appears beside the Library when possible.
2. The user moves/resizes/snaps it using system controls.
3. Images are contained without cropping by default.
4. Videos show their poster until ready, then auto-play.
5. Previous/Next are available in an ornament.
6. A horizontal look-pinch-drag navigates when its distance or velocity threshold is
   met.
7. The next card is already decoded or downloaded when prefetch succeeds.

### Make a 2D image spatial

1. Open a compatible image.
2. Air tap **Make Spatial**.
3. Keep showing the 2D image while RealityKit generates.
4. Transition to `.spatial3D` when generation succeeds.
5. Move the head slightly to experience parallax.
6. Select **Disable Spatial** to return to 2D and clear both the spatial and
   favorite preferences.
7. Navigate away without altering the backend original; generated spatial scenes
   remain available in a bounded cache for the current app session.

### Return later

1. Relaunch the app.
2. Library and an eligible last-open Media card restore through system scene
   restoration.
3. Each restored scene retains its window identity and user placement.
4. Missing media produces a recoverable placeholder, not a broken scene.

## Functional requirements

### Authentication and connection

- **XR-AUTH-001:** The app MUST accept a user-configured HTTP or HTTPS base URL.
- **XR-AUTH-002:** The app MUST validate unauthenticated health and authenticated
  session separately.
- **XR-AUTH-003:** V1 MUST accept a pasted bearer API token.
- **XR-AUTH-004:** The token MUST be stored only in Keychain.
- **XR-AUTH-005:** Tokens, prompt/media bodies, and full authenticated URLs MUST be
  redacted from logs.
- **XR-AUTH-006:** Disconnect MUST clear Keychain and local media cache only after
  confirmation.
- **XR-AUTH-007:** An expired/revoked token MUST preserve scene placement and return
  to Connect.

### Spatial scenes and anchoring

- **XR-SCENE-001:** Library MUST use a standard resizable window in Shared Space.
- **XR-SCENE-002:** Viewer MUST use one auxiliary resizable window.
- **XR-SCENE-003:** Both scenes MUST have stable IDs and scene restoration enabled.
- **XR-SCENE-004:** Connect MUST opt out of restoration.
- **XR-SCENE-005:** The app MAY suggest the Viewer's initial placement relative to
  Library but MUST accept system/user placement.
- **XR-SCENE-006:** Window movement, snapping, locking, and recentering MUST use
  system behavior.
- **XR-SCENE-007:** MVP MUST NOT start an Immersive Space or ARKit session.
- **XR-SCENE-008:** The app MUST open no more than one Media card.

### Library

- **XR-LIB-001:** Library MUST paginate `GET /api/v1/media`.
- **XR-LIB-002:** Grid MUST use adaptive columns and 2:3 visual cells.
- **XR-LIB-003:** Cells MUST show preview content, a video indicator, and only
  minimal state needed for browsing.
- **XR-LIB-004:** Cells MUST NOT show filenames, UUIDs, hashes, model/workflow
  metadata, or source paths.
- **XR-LIB-005:** Air tap MUST open or update the single Media card.
- **XR-LIB-006:** Media type, Favorites/Spatial, Trash, sort, page state, and scroll
  anchor MUST survive ordinary
  scene restoration.
- **XR-LIB-007:** Duplicate IDs received across shifting offset pages MUST be
  deduplicated.
- **XR-LIB-008:** Page failure MUST preserve already loaded content and offer Retry.
- **XR-LIB-009:** A refresh MUST not reorder an active Media-card neighbor sequence
  underneath an in-progress drag.

### Viewer

- **XR-VIEW-001:** Image presentation MUST preserve aspect ratio and contain by
  default.
- **XR-VIEW-002:** Viewer MUST respond continuously to window resize.
- **XR-VIEW-003:** Video MUST use the system AVKit playback interface.
- **XR-VIEW-004:** A newly active video MUST auto-play after it becomes ready.
- **XR-VIEW-005:** Leaving a video MUST pause it, cancel observers, and release its
  player when outside the neighbor cache.
- **XR-VIEW-006:** Only active media may produce audio.
- **XR-VIEW-007:** Loading, offline, unsupported, missing, and retry states MUST fit
  within the card without opening another window.
- **XR-VIEW-008:** Viewer MUST remain useful when Library is closed.

### Navigation

- **XR-NAV-001:** Viewer MUST expose Previous and Next buttons.
- **XR-NAV-002:** Viewer MUST support a standard horizontal `DragGesture` initiated
  by look plus pinch.
- **XR-NAV-003:** Gesture navigation MUST require a clear distance or velocity
  threshold and spring back when canceled.
- **XR-NAV-004:** A gesture MUST NOT be the only navigation method.
- **XR-NAV-005:** Dragging the AVKit transport controls MUST NOT navigate.
- **XR-NAV-006:** Navigation MUST use the current Library filter/sort scope.
- **XR-NAV-007:** Navigation MUST cross unloaded Library page boundaries.
- **XR-NAV-008:** At the scope boundary, the unavailable direction MUST be disabled.
- **XR-NAV-009:** New navigation MUST cancel obsolete current-media loads and
  deprioritize obsolete prefetch.

### Preload and caching

- **XR-CACHE-001:** Grid MUST prefetch only a bounded number of near-visible
  previews.
- **XR-CACHE-002:** Viewer MUST prioritize current media, then next, then previous.
- **XR-CACHE-003:** Image prefetch MUST decode to an appropriate display target, not
  retain unbounded originals in memory.
- **XR-CACHE-004:** The full original MAY be cached on disk for Make Spatial.
- **XR-CACHE-005:** Video prefetch MUST respect a byte budget; large videos may defer
  full download until selected.
- **XR-CACHE-006:** Spatial-scene generation MUST NOT occur during neighbor prefetch.
- **XR-CACHE-007:** Disk caches MUST use LRU eviction and be clearable.
- **XR-CACHE-008:** Memory pressure MUST release non-visible decoded images,
  generated scenes, and players.
- **XR-CACHE-009:** Cache identity MUST include server profile, media UUID, and
  resource kind.

### Spatial scene generation

- **XR-3D-001:** Make Spatial MUST be available only for images.
- **XR-3D-002:** The app SHOULD preflight documented pixel/aspect constraints before
  enabling generation.
- **XR-3D-003:** Generation MUST use a local authenticated download of the gallery
  original or a valid `CGImageSource`.
- **XR-3D-004:** Generation MUST be explicit and cancelable.
- **XR-3D-005:** Viewer MUST remain in 2D until generation succeeds.
- **XR-3D-006:** Successful generation MUST use `.spatial3D` in the existing Media
  card.
- **XR-3D-007:** Disable Spatial MUST remain available after generation and MUST
  clear both the spatial and favorite preferences.
- **XR-3D-008:** A generation error MUST leave ordinary 2D viewing intact.
- **XR-3D-009:** Generated data MUST NOT overwrite, re-encode, or upload a replacement
  for the server original.
- **XR-3D-010:** The app MUST explain that depth is generated and may contain
  artifacts.
- **XR-3D-011:** Device tests MUST cover minimum/maximum dimensions, aspect boundary,
  cancellation, artifact fallback, and repeated viewing.

### Lifecycle and accessibility

- **XR-LIFE-001:** Closing the Media card MUST stop playback and generation.
- **XR-LIFE-002:** Background/inactive scenes MUST stop audio and pause prefetch.
- **XR-LIFE-003:** Restoration MUST tolerate deleted media and revoked auth.
- **XR-ACC-001:** Every gesture action MUST have a visible system control equivalent.
- **XR-ACC-002:** Interactive target size/spacing MUST satisfy spatial eye-target
  guidance.
- **XR-ACC-003:** Cards and buttons MUST use system hover effects.
- **XR-ACC-004:** VoiceOver, Switch Control, Dwell Control, and pointer alternatives
  MUST reach all MVP actions.
- **XR-ACC-005:** Reduce Motion MUST replace large sliding transitions with a restrained
  fade/short movement.
- **XR-ACC-006:** The app MUST avoid head-locked UI and custom repetitive hand
  gestures.

## Performance targets

- Air tap produces visual acknowledgment within one frame of UI processing.
- Cached neighboring images transition without a blank card.
- On a healthy LAN, an uncached several-megabyte image or video should normally
  become viewable within two seconds.
- Grid scrolling and hover remain responsive while paging and prefetching.
- At most four preview downloads and one high-priority full-media download run
  concurrently by default.
- Only current and immediate neighbor full media are eligible for eager preparation.
- Spatial generation never runs more than one task at a time.
- The default disk media budget is configurable; 2 GiB is a reasonable starting
  point for device testing.

Targets must be measured on physical Vision Pro with representative image/video
files. They are not permission to hide truthful loading states.

## Acceptance scenarios

1. Place Library on a wall, lock it, relaunch, and confirm the scene restores
   correctly through system behavior.
2. Open Media card, resize from landscape to portrait proportions, and confirm the
   media remains contained and controls remain reachable.
3. Air tap an image at the end of a loaded page and navigate Next into an unloaded
   page without returning to Library.
4. Drag less than threshold and confirm the card returns to the same media.
5. Drag past threshold and confirm only one navigation occurs.
6. Use buttons to perform the same navigation with Dwell/VoiceOver.
7. Open a video, confirm auto-play, navigate away, and confirm its audio stops.
8. Lose Wi-Fi while viewing cached media; preserve the card and recover on Retry.
9. Generate a compatible image spatially on physical hardware, then return to 2D.
10. Cancel spatial generation by navigating away and confirm no stuck task/UI.
11. Attempt incompatible dimensions/aspect and confirm Make Spatial is unavailable
    or fails safely.
12. Revoke the token, relaunch restored scenes, authenticate again, and recover the
    same Library/Media context.
13. Inspect UI and logs and confirm no bearer token, filename, UUID, model/workflow
    data, or private gaze coordinate appears.
