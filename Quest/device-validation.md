# Quest implementation evidence

## Desktop build — 2026-09-17

Status: **build and deterministic logic verified; no headset installation or
physical test performed**. `adb devices -l` returned an empty target list.

Host: macOS arm64. Branch: `codex/quest-app-planning` (uncommitted implementation).
No live Gallery credentials or private media were used for these checks.

| Component | Recorded version/configuration |
| --- | --- |
| JDK | Homebrew OpenJDK 17.0.20.1 |
| Android command-line tools | 15859902 |
| Android SDK | compile 35; minimum/target 34; build tools 35.0.0 |
| Meta Spatial SDK | 0.14.0; declared minimum/target Horizon OS 69 |
| Gradle / Android plugin | 9.4.1 / 8.11.1 |
| Kotlin / Compose BOM | 2.1.0 / 2024.09.03 |
| Media3 / Coil | 1.4.1 / 2.7.0 |
| APK architecture | arm64-v8a |
| App | `com.comfygallery.quest`, 0.1.0 (version code 1) |

The application uses programmatic panels, so it does not require the Meta scene
exporter or custom shader build plugin. Android Studio and Meta Spatial Editor
were not installed for this build.

### Reference sample

Repository: [Meta-Spatial-SDK-Samples](https://github.com/meta-quest/Meta-Spatial-SDK-Samples).
Pinned commit: `f233e2327b95f9871b75bdba867d6fdd726f07cc`.
Unmodified project: `MrukSample`.

With JDK 17, SDK platform 34 and NDK `27.0.12077973`, running
`./gradlew :app:assembleDebug --console=plain` in that sample succeeded. The first
attempt identified the missing NDK; installing it resolved the failure. No source
changes were made to the sample. Its panel/controller behavior was not exercised.

### Gallery client

From `Quest/`, with JDK 17 and the configured Android SDK:

```sh
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease :app:lintDebug
```

Result: **BUILD SUCCESSFUL**, 17 tests, 0 failures; Android lint: 0 errors,
19 warnings. Warnings cover the deliberately pinned sample-era dependencies,
Android target 34, Quest-only ABI, and optional SharedPreferences KTX style.
These are recorded, not treated as headset or public-store approval.
Gradle also reports plugin APIs deprecated for Gradle 10; the wrapper stays at
the tested 9.4.1 version.

Checks cover:

- Authenticated JSON and ranged media requests using a local MockWebServer;
  no credential forwarding across redirects, origins, ports or path prefixes.
- Additive fields, 401 handling, and image caps for known/chunked lengths.
- Raw paging offsets, filtered/duplicate items, bounded filtering-only batches,
  late filter completion, and stale selection rejection.
- Captured-scope neighbor traversal, cycle recovery, Favorite-only anchor removal,
  late Favorite errors and callbacks after disconnect.
- Image-ready timing, explicit resume after focus loss, sequence priority over
  Loop, stale end-of-video callbacks and final-item stop.

This exercises the client's request/state boundaries. It does **not** exercise
ExoPlayer decoding, native spatial entities, Android Keystore, Compose rendering,
or actual controller input. There is no live-backend end-to-end result yet.

Artifacts are ignored local build output:

| Artifact | Signing | SHA-256 |
| --- | --- | --- |
| `app/build/outputs/apk/debug/app-debug.apk` | Local Android debug key | `a56006b2e72c5be5d237021812d85c4f405e373d9d2495c5f8bce73302cbedaf` |
| `app/build/outputs/apk/release/app-release-unsigned.apk` | Unsigned | `8195388d592fbcb4f35a43de5df7473b58b5ce071212de5f8e674f8dc67c7100` |

The debug APK signature was checked with Android `apksigner`. Manifest/package
metadata was inspected with `aapt`. No install command has run without a target.

## Physical installation — 2026-09-17

The user connected and authorized a Quest 3 over USB. Android reports version 14,
API 34, build `UP1A.231005.007.A1`, incremental build `52433670036000520`.
The user-facing Horizon OS version has not been independently identified.

Installed the debug APK with SHA-256
`a56006b2e72c5be5d237021812d85c4f405e373d9d2495c5f8bce73302cbedaf`
using `adb install -r`, which returned **Success**. Package manager confirms
`com.comfygallery.quest`, version 0.1.0 / code 1, installed and enabled.

Launching `.QuestActivity` initially opened Quest's controller-required launch
prompt. It subsequently cleared; Activity Manager confirmed the Gallery activity
resumed and its process running. No process exit or fatal app exception was
reported during this startup check.

App-scoped logs contain Meta runtime errors/warnings for the introspection native
hook, unavailable environment-depth entry points, initial renderer readiness,
swap behavior and controller render-model lookup. These did not terminate the
observed process; their effect on visible rendering/input remains unverified.
Do not treat the running process as a clean visual or controller acceptance.

No Gallery credentials were entered by the agent, and no ordinary-media playback,
stereo, controller interaction or visual scene inspection was performed. The
reference sample remains uninstalled. No headset serial is recorded here.

## 0.2.0 feedback revision — 2026-09-17

The user reported that 0.1.0 generally works, but windows cannot be moved, the
gallery viewport is small and requires manual loading, and the player is small
relative to its controls. They requested private built-in connection values.

Prepared 0.2.0 / version code 2 with:

- Explicit ISDK Direct movement, frame grab handles and native resize corners.
  Library resizing uses Relayout; media resizing preserves aspect. The media
  frame now owns movement, with controls attached below and counter-scaled.
- Library 1.8 × 1.65 m, adaptive columns, compact filters and near-end automatic
  page fetching. Error retries and four-page scans with no visible progress
  require explicit continuation to prevent repeated network work.
- Media frame 2.8 × 1.68 m and controls 1.9 × 0.34 m. Volume and Loop are in Options.
- An ignored `private-connection.properties` config, embedded only in the debug
  APK. The configured Connect to my Gallery action avoids headset typing.

The supplied local config was saved by the user. Its values match the generated
debug defaults; neither value is recorded here. A desktop reachability check and
authenticated session request each returned HTTP 200 without following redirects.
Release-generated defaults were verified empty. This is a desktop transport
check, not proof of the headset's network path or native input behavior.

Desktop command:

```sh
./gradlew :app:assembleDebug :app:assembleRelease :app:testDebugUnitTest :app:lintDebug
```

Result: BUILD SUCCESSFUL; **21 tests, 0 failures; lint 0 errors, 19 warnings**.
New tests cover near-end automatic fetching without a button, single-flight
loading, error retry suppression, filtered-batch stopping, fitted video ratios,
and a constant physical gap between resized media and its controls. Two paging
tests were first run against the missing automatic-load behavior and failed,
then passed after implementation. Debug signature and 0.2.0 package metadata
were verified. Current APK hashes (the output paths overwrite the 0.1.0 artifacts):

- Debug: `b804de005bf5a4aca4715c550167246338e41c4b85120f51e09d3b1f838616be`
- Unsigned release: `09a4cf7d1dc748b976a7bb02a362a70dd6ed7e237d6fec1a1a500cd74d4c7874`

The user chose **prepare the APK; test later**. No 0.2.0 install was attempted.
The controller check script was prepared from the human-in-the-loop diagnostic
workflow. Running `bash scripts/check-panel-interaction.sh --check-device`
returned `DEVICE=unavailable`, `RESULT=not_run` (exit 2). Full native movement
reproduction, ranked-cause testing and physical fix verification are deferred
under that instruction; the original root cause is not established. The explicit
component setup follows the pinned SDK's documented panel customization path:
[Meta panel interaction](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-isdk-panels/)
and [0.14 grab handles](https://developers.meta.com/horizon/reference/spatial-sdk/v0.14.0/com_meta_spatial_isdk_isdkpanelgrabhandle/).

For the next headset session, run `bash scripts/check-panel-interaction.sh` from
`Quest/` and record its actual movement/resize/paging outcomes. The script logs no
connection values or private media. A successful desktop build is not a pass for
that test.

## 0.3.0 placement and video scale correction — 2026-09-18

The user reports that 0.2.0 windows resize, but video does not resize and windows
appear fixed in position/orientation. ADB confirms installed 0.2.0 / code 2.
This is user-reported physical evidence, not an agent-observed controller trace.

The scene used `TransformParent` as if it inherited scale. The pinned SDK's
`TickTransformSystem.applyScale` defaults to false; `ScaleSystem` applies each
entity's own scale. The video had no explicit Scale component. The controls also
used inverse scale and an offset divided by scale, which assumed a different
parenting model. 0.3.0 explicitly keeps pose-only parenting, copies the frame's
X/Y scale to the video on creation and resize, and leaves controls at scale 1
with their position below the actual scaled frame.

The corrected controls regression command was run before the fix:

```sh
./gradlew :app:testDebugUnitTest --tests com.comfygallery.quest.PanelLayoutTest --console=plain
```

It returned `2 tests completed, 1 failed` for the constant-gap assertion. After
the fix it passes. This tests the application geometry under the SDK parenting
contract; it does not measure native video rendering or pointer input.

New Position actions support Bring here, Face me, Closer/Farther, and directional
placement. The Viewer adds Smaller/Larger. Startup and reset are relative to the
tracked head. Native grab handles are wider and in front of the video, and use
Billboard movement. The native grab failure's cause remains unconfirmed: the
side-grip clarification did not receive a response during this build. The human
check was started but stopped awaiting input; no result was invented. The updated
`scripts/check-panel-interaction.sh --check-device` returns `DEVICE=ready`.

Final desktop command:

```sh
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease :app:lintDebug --console=plain
```

Result: BUILD SUCCESSFUL, **25 tests pass**, lint **0 errors / 19 warnings**.
Placement tests cover translated/turned heads, panels facing the viewer,
bounded distance changes and vertical-gaze fallback. Debug APK signature and
version 0.3.0 / code 3 metadata are verified. Output paths are unchanged:

- Debug SHA-256: `e72e27044763647a9a0e6b0e8a4979d5de3202e03d2154fcead5654c06d2a9de`
- Unsigned release SHA-256: `3a2f45f4678e6d278d527aa6a3fb56cff5e615c3c5d3d174313863da081c9878`

Following the user's APK-preparation preference, 0.3.0 has **not** been installed
by the agent. Next physical check: side-grip frame movement, Bring here after
turning/repositioning the head, video corner/button resizing, and replacement
videos keeping the chosen size. Run the updated check script. Do not treat the
desktop checks as physical acceptance.

## Physical-device checklist

Installation and process startup are verified above; the functional rows below
remain **pending**. The Quest is authorized for USB debugging. Use the commands
in [README](README.md#build-and-install) for subsequent updates.

Record headset model/OS, app hash, server version, sanitized media properties,
steps and result. Keep credentials and private media outside checked-in evidence.

| Area | Exercise | Pass criteria |
| --- | --- | --- |
| Launch/scene | Cold launch, recenter, system menu | Passthrough and both panel groups appear; no native crash. |
| Either controller | Connect text entry, grid selection, scrolling/Page up/down, panel grip and resize/reset | Complete the flow seated with either controller alone; readable targets and no accidental locomotion. |
| Connection | HTTP LAN, HTTPS, path prefix, wrong/expired token, offline server, relaunch and Disconnect | Correct recovery; restore only the profile; Disconnect clears credentials and work. |
| Library | Large library, every filter/order, rapid filter changes, repeated paging and preview failures | Correct order/offsets; no stale items or unbounded fetching. |
| Images | Portrait, landscape, large dimensions, missing file, oversized original | Aspect-fit; bounded memory and explicit recovery. Current decode is at most a 1920×1152 target, 64 MiB transfer and cache limits. |
| Ordinary video | Gallery proxy/original, landscape/portrait, sound/silent files, play/pause, ranges and seek, Loop, volume | One decoder/audio source, correct aspect, responsive controls, no hidden full-library download. |
| Navigation/Favorite | Cross-page next/previous, unready neighbors, unfavorite in Favorites, removed anchor | Viewer scope retained; safe out-of-scope state and Library recovery. |
| Auto Play | Mixed images/video, manual next/previous, Loop on, final item, failures | Five-second dwell after image ready; sequence overrides repeat without changing Loop preference; no error-driven runaway skipping. |
| Lifecycle | Rapid open/close/reopen, switch selection during loading/seek, system menu, headset removal, tracking loss, disconnect | Old callbacks cannot affect new content; inactive playback pauses and requires explicit resume. |
| Performance | Sustained use on a signed release build | Record frame pacing, peak memory, first-frame and seek latency before setting release budgets. |
| Optional spatial | A real Gallery MV-HEVC variant through a proposed compatible player | Verify both eyes, eye order, aspect/depth, seek/audio/lifecycle. Keep feature disabled until proven. |

## Remaining implementation decisions

- Validate focused passthrough placement and SDK grip/ray behavior before
  adding focus-routed thumbstick and B/Y shortcuts. Visible controls already
  represent all core actions in the first APK.
- Tune cache/decode/surface budgets and add measured neighbor prefetch. Current
  conservative image caps are implementation defaults, not benchmark results.
- Decide private release signing and install a signed release for acceptance.
- Assess dependency upgrades after the initial pinned baseline runs on Quest.
- Keep Q6 optional. No backend role/schema/preference changes or SBS substitution
  were made. The availability badge is not evidence of stereo support.

Continue under [Quest tracker #17](https://github.com/blkot/ProjectComfyGallery/issues/17).
