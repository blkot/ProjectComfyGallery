# Quest architecture and development plan

**Status:** First implementation, 2026-09-17. The reference sample and client
build on macOS, and the debug client is installed and running on Quest 3.
API/state tests pass; Q1 controller/media hardware acceptance is still open.
Source work advanced in parallel with the toolchain check under the user's
implementation authorization. See [device evidence](device-validation.md).

## Architecture baseline

Start with Kotlin, Compose, Meta Spatial SDK, and Media3/ExoPlayer. This follows
the [research](../doc/research/quest-3-development-research.md); it remains subject
to the Q1 device feasibility check. Unity/OpenXR is the fallback if core panel,
controller, or ordinary-media behavior proves unsuitable. Optional stereo failure
alone is not grounds to replace the whole client stack.

Use one Android app module initially, organized by responsibility:

| Area | Owns | Boundary |
| --- | --- | --- |
| Connection/data | Profile, credentials, HTTP, typed contract, paging, detail/navigation, Favorite | No scene entities or UI widgets. |
| Library | Scope, grid state, request generations, thumbnails | Does not own video playback. |
| Viewer/media | Selection, one active player, sequence, representation policy, cache/prefetch | Does not own backend availability or conversion. |
| Quest scene/input | Panels, focus, controller actions, placement, activity lifecycle | Dispatches semantic actions; does not perform API calls. |

Keep optional representation policy at the player boundary. Do not duplicate the
Gallery client for spatial content or introduce a separate app for stereo.
Use dependency injection at useful seams (transport, credentials, resource
loading, clock/player events); a multi-module framework is unnecessary initially.

## Planned repository shape

The Android Gradle project, wrapper, version catalog, app module, resources and
tests now live here. The application ID is `com.comfygallery.quest`. Debug builds
use the local Android debug key; release signing is external to the repository.

Keep source under the app module using the four areas above. Add sanitized API
fixtures with the tests and a device evidence document after real checks run.
Ignored local media and SDK settings are not release artifacts.

## Milestones

### Q0 — Planning and project boundary

- [x] Create `codex/quest-app-planning` and `Quest/`.
- [x] Capture product, UI/controller, API, architecture, and validation plans.
- [x] Register Quest context in repository navigation and agent instructions.
- [ ] Settle Home panels versus the focused scene before final scene implementation.

Exit: a reviewable plan with explicit assumptions and separate core/optional
acceptance. The scene choice does not prevent Q1 feasibility work.

### Q1 — Toolchain and physical-device feasibility

- [x] Select the actual host and inspect Android Studio/JDK/SDK/ADB setup.
- [x] Select a current Meta sample; pin sample commit and compatible
  Gradle/Android/Compose/Meta/player versions, including minimum Horizon OS.
- [x] Configure Quest developer access and verify a physical USB ADB target.
- [x] Install the Gallery debug APK and verify the activity starts on Quest 3.
- [x] Build the unmodified sample; record the command and outcome.
- [ ] Install the reference sample on Quest.
- [ ] Verify readable panels, ray selection, one-controller operation, panel
  movement, and ordinary video with audio on Quest 3.
- [x] Create the project scaffold under `Quest/`, retaining required sample licenses.
- [x] Record desktop versions, commands, outcomes, and unresolved limits.
- [ ] Record headset OS and physical-device results.

Exit: a standalone build establishes that the core stack works. If it does not,
document the narrow failure and evaluate Unity before deeper client work.
Do not require optional MV-HEVC success for this exit.

### Q2 — Connection and API foundation

- [x] Implement profile, protected token storage, cancellation, and redacted errors.
- [ ] Verify LAN transport policy and same-origin media authentication.
- [x] Implement narrow models and repository contract from the API document.
- [x] Test auth headers/rejection, redirects, profile isolation, and unknown fields on desktop.
- [ ] Test saved connection restoration and unreachable server recovery on Quest.
- [ ] Exercise URL/token onboarding using only controllers in the headset.

Exit: the intended gallery connects, survives relaunch, and fails recoverably.
Maps to Q-CON-01/02 and the authentication portion of Q-ERR-01.

### Q3 — Library and input

- [x] Build grid, loading states, kind/Favorite/order controls, and Refresh.
- [x] Implement raw-offset paging, status filtering, deduplication, and stale-request rejection.
- [x] Add near-end automatic loading with explicit recovery after errors or filtering-only batches.
- [x] Implement explicit native panel grab/resize frames, larger adaptive Library and compact Viewer controls in 0.2.0.
- [x] Correct video scale propagation and add head-relative placement/size controls in 0.3.0, with desktop geometry tests.
- [ ] Verify frame movement, corner resizing, controller selection and reset on device.
- [x] Test scope changes during paging and filtering-only batches on desktop.
- [ ] Test empty/failed pages and preview failures in the headset UI.

Exit: a representative large library is usable on Quest with either controller.
Maps to Q-LIB-01/02/03 and Q-IN-01.

### Q4 — Ordinary Viewer and release candidate

- [x] Implement one Viewer, aspect-fit images, and ordinary video/audio integration.
- [ ] Verify authenticated streaming, seek, mute/volume, and Loop on real files.
- [x] Add scoped Previous/Next and Favorite with out-of-scope/error reconciliation.
- [x] Implement generation-owned callbacks, teardown, and initial bounded image resources.
- [ ] Add measured prefetch and tune resource budgets on the headset.
- [ ] Exercise open/close/reopen, rapid navigation, headset removal, focus changes,
  network loss, expired auth, silent video, unsupported codec, and large images.
- [ ] Measure release frame pacing, memory, load/seek latency; set media limits
  and budgets from the device results.

Exit: core acceptance in the product document passes on the installed release
build. Maps to Q-VIEW-01/02/03, Q-NAV-01, Q-FAV-01, Q-LIFE-01, Q-ERR-01.
This is a useful deliverable without Q6.

### Q5 — Filtered auto-play

- [x] Implement captured-scope, five-second-image, video-end sequence behavior.
- [x] Test sequence precedence over Loop, explicit resume, final-item stop,
  cancellation, and unplayable neighbors on desktop.
- [ ] Validate manual navigation and failure recovery in the headset UI.
- [ ] Validate sustained mixed-media auto-play in the headset.

Exit: Q-SEQ-01 passes without regressing single-item controls or resource limits.
This feature is independent of spatial formats.

### Q6 — Optional spatial player

- [ ] Evaluate the intended public player with an actual Gallery MV-HEVC variant.
- [ ] Verify both eyes, eye order, aspect/depth, embedded audio when present,
  seeking, Loop, lifecycle, and repeated ordinary/spatial switching.
- [ ] Add explicit local Play Spatial/Play in 2D for a validated capability path.
- [ ] Verify fallback and unchanged server Favorite/preference/availability.
- [ ] If direct playback is unsuitable, document the result and defer the feature
  or scope a separate SBS representation proposal with the backend owner.

Exit: Q-SP-01/02/03/04 has physical evidence, or spatial playback stays deferred
while the ordinary client remains deliverable. External conversion and shared
schema work are not hidden prerequisites of Q1–Q5.

## Evidence and tests

Use focused tests for stateful behavior: paging scope ownership, playable-neighbor
traversal, stale player callbacks, auth changes, representation fallback, sequence
timing and Loop arbitration. Test observable behavior, not SDK internals.
Integration checks cover Gallery responses and range/auth delivery. Hardware
checks cover decoder output, controls, comfort, surface lifecycle, audio, and
release performance.

Record each device session's app commit/build, SDK/player versions, Quest OS,
server version, sanitized fixture properties, steps, result, and remaining
problems. Compilation, desktop simulation, and PC-rendered Link sessions are not
substitutes for standalone Quest acceptance.

Build commands and actual desktop results are in [README](README.md#build-and-install)
and [device validation](device-validation.md). Code checkmarks above represent
implementation or specifically named desktop tests. Milestone exits still
require their stated physical acceptance.

## Open decisions and dependencies

| Item | When needed | Working direction |
| --- | --- | --- |
| Focused scene or Home multitasking | Before final scene implementation | Focused scene for the first feasibility test. |
| Host/toolchain/headset access | Q1 | Inspect the chosen real machine and connected Quest. |
| Minimum OS and package versions | Q1 | Pin a compatible, device-tested set. |
| Cache budgets and media limits | Q4 | Measure representative files. |
| Spatial defaults | Q6 | Ordinary default, explicit local action. |
| Direct MV-HEVC or fallback format | Q6 | Test the existing representation first. |

Use a dedicated Quest issue for execution coordination. Shared format changes
must preserve [ADR-0011](../doc/decisions/0011-imported-media-variants.md) and the
external-conversion boundary in [ADR-0014](../doc/decisions/0014-event-driven-mss-orchestration.md).
Updates on historical #2 do not reopen its completed Apple-specific workstream.
