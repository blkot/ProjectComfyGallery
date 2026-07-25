# Mobile Product Requirements

**Status:** Accepted handoff scope  
**Audience:** Product designer, iOS developer, QA engineer, and coding agent

## Product statement

Project Comfy Gallery Mobile is a private LAN companion for visually browsing the
gallery and completing manual blind evaluations from an iPhone. It should feel like
picking up a small, interruption-friendly review queue: open the app, continue where
you stopped, score one or many items, and leave without ceremony.

## Primary user and context

The V1 user is the owner of one self-hosted Project Comfy Gallery server. The user
reviews during short or long periods of free time and may stop because the app is
backgrounded, the phone locks, network connectivity changes, or they simply decide
to continue another day.

The typical server is reachable over a trusted local network. Images and videos are
usually several megabytes. The mobile client must not assume CUDA, cloud services,
internet connectivity, or an always-running ComfyUI instance.

## Goals

- Make visual browsing pleasant on a phone.
- Make repeated blind scoring faster than using a desktop browser on a phone.
- Preserve the same evaluations, revisions, Trash state, and review sessions as the
  web application.
- Make every successfully committed score durable immediately.
- Preserve locally committed-but-unsent work through ordinary interruption.
- Keep experiment-revealing configuration out of the review experience.
- Use native media, accessibility, security, and lifecycle behavior.

## Non-goals

- Media import or upload.
- Workflow, node, checkpoint, LoRA, prompt-extraction, or registry administration.
- Filename, dimensions, codec, file size, UUID, SHA-256, source path, or workflow
  metadata display.
- Collections, tags, saved-filter editing, model comparison, or analytics.
- Editing evaluation templates or weighting profiles.
- ComfyUI control.
- Multiple users or inter-rater review.
- Full offline library synchronization.
- Automatic scoring or AI evaluation.
- Automatic navigation after scoring, completion, Trash, or restore.

## Product vocabulary

- **Library:** Visual-only grid of managed media.
- **Viewer:** Immersive image/video presentation without metadata or scoring.
- **Blind Review:** Prompt-aware evaluation surface whose server response excludes
  checkpoint, LoRA, workflow configuration, source, tag, and collection evidence.
- **Not started:** No applicable criteria resolved.
- **In progress:** At least one criterion resolved and at least one unset.
- **Complete:** Every applicable criterion is scored or N/A.
- **Trash:** Reversible disposition for failed generations; independent of progress.
- **Pending change:** A locally committed score/disposition command not yet
  acknowledged by the backend.

## Core user journeys

### Connect once

1. Enter or discover the gallery base URL.
2. Authenticate by pasting a device API token, or use the optional one-time pairing
   flow described in the API contract.
3. Verify the session against the server.
4. Store only the bearer token and normalized server URL.
5. Enter the Library.

### Browse visually

1. Open Library.
2. Scroll a portrait-oriented adaptive grid.
3. Optionally filter by image/video, evaluation progress, or Trash.
4. Tap an item to open the Viewer.
5. Swipe or explicitly move to adjacent items.
6. Return to the same grid position.

The client may receive extra metadata in a list response but must decode only the
fields it uses and must not render experiment or file metadata.

### Start blind review

1. Open Review.
2. Choose one of:
   - Continue the most recently active session.
   - Resume the global In progress pool.
   - Start random unevaluated media.
   - Start from the current visual Library filter.
3. Choose a maximum item count.
4. Optionally include the Character rubric.
5. Create a server-side review session and open its saved cursor.

### Evaluate continuously

1. View the media in the largest practical stage.
2. Read the exact extracted prompt when needed.
3. Resolve criteria using integer sliders, N/A, or Clear.
4. See an unobtrusive local/saving/saved/error state.
5. Explicitly select Previous or Next.
6. Optionally mark or restore Trash without moving.
7. Stop at any time.

### Resume

1. Reopen the app.
2. The Review tab presents Continue for the last active session.
3. Open the saved server cursor, reconciled with any local pending change.
4. Continue with no streak, deadline, or completion pressure.

## Functional requirements

### Connection and security

- **MOB-AUTH-001:** The app MUST support a user-configured HTTP or HTTPS base URL.
- **MOB-AUTH-002:** The app MUST validate connectivity with `/health/live`.
- **MOB-AUTH-003:** The normal authenticated mode MUST use a bearer API token.
- **MOB-AUTH-004:** The bearer token MUST be stored in Keychain and excluded from
  logs, analytics, crash messages, screenshots, and persisted request fixtures.
- **MOB-AUTH-005:** Disconnect MUST erase the Keychain token, local media cache,
  pending commands, and active server profile after explicit confirmation.
- **MOB-AUTH-006:** An authentication failure MUST return to a reconnect state without
  destroying server-side review progress.

### Library and viewer

- **MOB-LIB-001:** Library MUST show images and video posters in an adaptive visual
  grid with a default 2:3 cell.
- **MOB-LIB-002:** Library MUST paginate rather than loading the entire database.
- **MOB-LIB-003:** Grid cells MUST NOT show filenames, identifiers, model names,
  workflow information, or file facts.
- **MOB-LIB-004:** A small video glyph, Trash treatment, and evaluation-progress
  treatment MAY be shown because they support interaction and do not reveal
  experiment configuration.
- **MOB-LIB-005:** Viewer MUST contain the media within the current safe viewport and
  MUST NOT cover it with navigation controls.
- **MOB-LIB-006:** Images MUST support double-tap zoom, pinch zoom, and pan.
- **MOB-LIB-007:** Videos MUST support play/pause, seek, mute/volume through system
  controls, and replay.
- **MOB-LIB-008:** Returning from Viewer MUST preserve the Library filter and scroll
  position.

### Review session

- **MOB-REV-001:** Review MUST use the backend review-session endpoints.
- **MOB-REV-002:** Review MUST fetch items only through the blind
  `/review-sessions/{id}/items/{position}` projection.
- **MOB-REV-003:** While Review is visible, the client MUST NOT fetch media detail,
  workflow, registry, collection, tag, source, or analysis endpoints.
- **MOB-REV-004:** Review MUST show exact extracted prompt fields.
- **MOB-REV-005:** Review MUST show every criterion returned by each applicable
  evaluation, including supplemental modules selected for the session.
- **MOB-REV-006:** Criterion values MUST support Unset, N/A, and integer 0–10.
- **MOB-REV-007:** Zero MUST remain visually and semantically distinct from Unset.
- **MOB-REV-008:** Clear MUST delete the saved score and return the criterion to
  Unset.
- **MOB-REV-009:** Score, Clear, Trash, and Restore MUST include the latest
  `expected_version`.
- **MOB-REV-010:** Completion MUST derive from the authoritative evaluation response.
- **MOB-REV-011:** Completion, Trash, and Restore MUST NOT navigate automatically.
- **MOB-REV-012:** Previous and Next MUST update the server-side cursor only through
  an explicit user action.
- **MOB-REV-013:** The next review item and media SHOULD be prefetched after the
  current item is stable.
- **MOB-REV-014:** Stop MUST be available without abandoning or finishing the
  session.
- **MOB-REV-015:** Session deletion MUST never delete evaluations and MUST require
  confirmation.

### Durability and conflict handling

- **MOB-DATA-001:** A control change MUST update the local UI immediately.
- **MOB-DATA-002:** Before network transmission, the committed change MUST be written
  to a local pending-command record.
- **MOB-DATA-003:** A successful response MUST replace the local evaluation with the
  authoritative server representation and remove the pending command.
- **MOB-DATA-004:** Navigation MAY wait for the current item to reach Saved state;
  it MUST never silently discard a pending command.
- **MOB-DATA-005:** HTTP `409 EVALUATION_VERSION_CONFLICT` MUST NOT be retried as an
  overwrite. The app MUST fetch current state and offer Reload or Reapply.
- **MOB-DATA-006:** Network loss MUST show Saved locally and retry with bounded
  backoff when connectivity returns.
- **MOB-DATA-007:** Server data remains authoritative after reconciliation.
- **MOB-DATA-008:** Pending commands belong to one server profile and MUST never be
  sent to another base URL.

### Lifecycle

- **MOB-LIFE-001:** The last active tab, review-session ID, and position MUST restore
  after ordinary termination.
- **MOB-LIFE-002:** Backgrounding MUST pause nonessential prefetch and attempt a
  bounded pending-write flush.
- **MOB-LIFE-003:** Foregrounding MUST verify session availability and reconcile the
  visible review item.
- **MOB-LIFE-004:** Phone lock or app termination MUST not mark a review session
  finished or abandoned.

## Experience and performance targets

- Cached grid content remains responsive at 60 fps on a currently supported iPhone.
- Slider movement and integer selection produce no network-driven UI stalls.
- A cached image appears effectively immediately.
- On a healthy LAN, the current image or video poster should normally appear within
  1.5 seconds.
- Only the current and next review media are eagerly prepared.
- Decoded images are downsampled to the display target rather than held at original
  dimensions.
- The disk media cache is bounded and clearable; a suggested default is 1 GiB.
- Memory pressure immediately releases non-visible decoded images and players.

These are engineering targets, not reasons to hide failures. Instrument with
signposts in debug builds and validate using representative portrait images and
videos.

## Accessibility requirements

- Support Dynamic Type without hiding score state or Save/Stop navigation.
- Every slider exposes criterion label, current state, value, and adjustable actions
  to VoiceOver.
- N/A, Unset, score, saving, error, and Trash states use text/symbols in addition to
  color.
- Respect Reduce Motion and Reduce Transparency.
- Maintain at least 44×44 pt interactive targets.
- Do not use horizontal swipes as the only navigation mechanism.
- Keep video controls accessible while the criteria content scrolls.

## Privacy requirements

- No third-party analytics or crash-upload service in V1.
- No media is uploaded to another service.
- Sensitive URLs, tokens, prompts, filenames, and media identifiers are redacted
  from logs.
- Consider a privacy cover when the app enters the app switcher; make it configurable
  because the gallery may contain sensitive media.
- Notifications, if ever added, must not include media or prompt content.

## Acceptance scenarios

1. Score `0`, background the app, reopen, and confirm the score remains `0`, not
   Unset.
2. Mark N/A, navigate away explicitly, return, and confirm it counts as resolved.
3. Clear a completed criterion and confirm the evaluation returns to In progress.
4. Mark Trash and confirm the same media remains visible until explicit navigation.
5. Complete the final unset criterion and confirm the same media remains visible.
6. Stop after one item, relaunch days later, and continue from the same cursor.
7. Lose Wi-Fi after moving a slider, leave the screen, reconnect, and verify the
   pending command is reconciled without silent loss.
8. Edit the same evaluation in the web app and mobile app; verify the stale mobile
   command surfaces a conflict rather than overwriting.
9. Inspect every Review screen and accessibility label and confirm checkpoint, LoRA,
   filename, UUID, hash, source, and workflow configuration never appear.
10. Review representative images and videos in portrait, landscape, large Dynamic
    Type, VoiceOver, Low Power Mode, and reduced network quality.

