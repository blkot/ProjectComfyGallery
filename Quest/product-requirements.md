# Quest product requirements

**Status:** Draft planning baseline, 2026-09-17. User-confirmed boundaries are
listed in [README](README.md#decision-register); other details are proposals.

## Product statement

A seated, controller-first spatial viewer for an existing self-hosted ComfyGallery.
The first useful version connects, browses, and plays ordinary media. It remains
fully usable without spatial variants, conversion services, or hand tracking.

## Core requirements

| ID | Planned behavior | Acceptance evidence |
| --- | --- | --- |
| Q-CON-01 | Connect to one configured gallery URL with an existing API token. | Valid token connects; wrong token and unreachable server have distinct recovery states. |
| Q-CON-02 | Persist the profile and protect credentials; disconnect cancels work. | Restart restores the profile; secrets do not appear in logs, URLs, fixtures, or backups of ordinary settings. |
| Q-LIB-01 | Browse a paginated mixed image/video grid. | Consecutive pages preserve server order, deduplicate by ID, and survive retry. |
| Q-LIB-02 | Provide All/Images/Videos, Favorite-only, Refresh, and newest/oldest order. Hide Trash. | Every request uses the selected scope; changing scope cannot append stale results. |
| Q-LIB-03 | Admit only `ready` and `ready_with_warnings` media. | Pages containing only other statuses do not strand pagination. |
| Q-VIEW-01 | Open one selected image or video in one Viewer. | Selecting a new item replaces the old selection and stops its audio/work. |
| Q-VIEW-02 | Fit images without cropping and preserve aspect ratio. | Portrait/landscape images render correctly, with bounded decode/cache memory. |
| Q-VIEW-03 | Play ordinary video with audio and persistent controls below it. | Play/Pause, seek, Loop, mute/volume, and close work using controllers on Quest. |
| Q-NAV-01 | Previous/Next uses the scope captured when the Viewer opened. | Navigation crosses page boundaries and skips non-playable records without cycles. |
| Q-FAV-01 | Favorite changes only through the Favorite command. | Successful writes reconcile the grid; failed writes roll back or remain visibly retryable. |
| Q-IN-01 | Every core flow works seated with either controller. | Connect, browse, open, playback, navigation, panel placement, and recovery need no hand gesture. |
| Q-LIFE-01 | Pause on loss of activity/focus and release closed/replaced media. | Repeated close/reopen, headset removal, and selection changes produce no stale playback or double audio. |
| Q-ERR-01 | Network/auth/media errors have bounded, explicit recovery. | Offline, 401, missing media, unsupported codec, and interrupted transfer do not crash or retry forever. |

The initial UI excludes Trash rather than offering destructive media actions.
Restoring a selection must not start audio until the app is active and the user
has re-entered the viewing flow. Exact restoration behavior is refined in Q4.

## Filtered auto-play

Q-SEQ-01 is a follow-on core milestone after ordinary viewing works. It reuses the
XR behavior: capture the current filter/sort scope, dwell on an image for five
seconds after it becomes ready, and advance video at end-of-item. Sequence
advancement takes precedence over Loop without overwriting the Loop setting.

Manual Previous/Next keeps the sequence active. Viewer close, disconnect, auth
loss, a current-media failure, or the final playable item stops it. Activity
inactivity suspends advancement; resume is explicit. This is a live filtered
view, not a saved editorial sequence or an immutable playlist snapshot.

## Optional spatial playback

- **Q-SP-01:** A compatible ready variant may expose an explicit Play Spatial
  action after physical-device validation of that player/format path.
- **Q-SP-02:** Play in 2D always returns to ordinary playback for the same media.
- **Q-SP-03:** Missing, unsupported, or failed spatial playback falls back to
  ordinary video without changing Favorite, availability, or shared preference.
- **Q-SP-04:** Backend spatial availability and local playability remain distinct.
  A base-eye-only decode does not satisfy stereo acceptance.

These requirements do not block core release. The default proposal is ordinary
playback plus a session-only spatial override. Automatic preference handling is
deferred until explicitly designed.

## Deferred scope

Hand tracking, eye-based selection, runtime 2D-to-depth image generation, room
scanning/anchors, persistent wall snapping, 180/360 environments, multiple media
viewers, offline library synchronization, evaluation/admin/workflow screens,
conversion controls, editing, and public-store distribution are outside the
initial plan. Collection/tag organization can follow the current backend contract
later; this client plan does not adopt unrelated proposed organization models.

## Quality and completion

Target readable panels and controller targets at a comfortable seated distance,
bounded caches, cancellable transfers, and one active video decoder/session.
Measure first-thumbnail, first-video-frame, seeking, frame pacing, and memory on
the actual headset during Q1/Q4 before setting quantitative release budgets.

Core completion requires a release build installed on Quest 3 against the
intended gallery, covering connection, paging, controller-only viewing, audio,
seek, lifecycle, and failure recovery. Desktop tests establish deterministic
logic; they cannot establish stereo quality, comfort, or headset performance.
