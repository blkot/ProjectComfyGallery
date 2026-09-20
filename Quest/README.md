# ComfyGallery for Quest

**Status:** User tested 0.2.0; 0.3.0 corrects video scaling and adds explicit placement controls. Device verification of 0.3.0 is pending.

**Started:** 2026-09-17

**Branch:** `codex/quest-app-planning`

**Target:** Standalone Quest 3, controllers as the primary input.

**Tracker:** [#17](https://github.com/blkot/ProjectComfyGallery/issues/17)

## Purpose

Browse the existing Gallery and view images and videos in a seated spatial
interface. Reuse the visionOS app's product design where it fits Quest. Ordinary
viewing is the core product; spatial-variant playback is optional. Once installed,
the app runs on Quest and connects directly to the Gallery server.

## Read in order

1. [Research and platform evidence](../doc/research/quest-3-development-research.md)
2. [Product requirements](product-requirements.md)
3. [UI and controller design](ui-ux-design.md)
4. [API and media contract](api-and-media-contract.md)
5. [Architecture and development plan](development-plan.md)
6. [Build evidence and device checklist](device-validation.md)

The backend remains authoritative. Compilation and desktop tests do not establish
device compatibility or complete the physical acceptance criteria.

## Implemented first pass

- Gallery URL/token onboarding, Android Keystore protection, connection restore,
  disconnect and cancellation. Tokens stay out of URLs, logs and backups.
- Ready image/video grid, kind/Favorite/order filters, Refresh, raw-offset paging,
  deduplication, adaptive columns and automatic loading near the grid end. Errors
  require Retry; long runs of unready-only pages pause with Continue searching.
- One image/video Viewer with scoped Previous/Next, Favorite, seek, Loop,
  mute/volume, close, native grab frames/corner resizing and reset layout. The
  larger media frame owns Viewer placement; video receives an explicit matching
  scale and controls keep their physical size below it. Position / Size offers
  Bring here, Face me, distance/directional adjustments, and Smaller/Larger.
  Startup and reset use the current head pose. Native behavior awaits the revised device test.
- Auto Play advances five seconds after image loading or at video end. It
  overrides looping while retaining the Loop preference. Focus loss pauses
  playback and stops Auto Play until explicitly resumed.
- Profile/selection ownership rejects stale responses. Authenticated media
  requests stay on the configured origin and path prefix; redirects are rejected.
  Images have a provisional 64 MiB transfer limit, 64 MiB memory cache, bounded
  decode dimensions, and no disk cache. Thumbnail traffic uses a separate
  two-per-host queue from API and video traffic.

The **Spatial variant stored** badge reports availability only. There is no Play
Spatial action until Gallery MV-HEVC two-eye playback is verified. Controller
stick shortcuts, prefetch, and measured performance tuning are follow-up work.
The user reports that the core app and window resizing work, but 0.2.0 video
resizing and panel placement do not. The 0.3.0 correction still requires the
headset checklist.

## Position and size (0.3.0)

- Open **Position** in Library or **Position / Size** below the Viewer.
- **Bring here** places that panel in front of your current viewpoint, facing you.
  **Face me** rotates it in place. **Closer/Farther** adjust distance; the directional
  buttons adjust position. These are one-shot actions, not head-locked windows.
- **Smaller/Larger** change the image/video frame while controls keep their size.
- For direct manipulation, aim at the outer frame and hold the controller's side
  grip. Grabbed panels are configured to face the viewer. Drag corners to resize.
- **Reset layout** arranges both panels around your current viewpoint, resets the
  Viewer size, and retains the Library's resized dimensions.

The grab region is wider and in front of the video surface. Exact controller
gesture behavior remains subject to the physical check; the visible position
actions provide a separate way to place panels using normal trigger clicks.

## Build and install

Use JDK 17, Android SDK platform 35 and build tools 35.0.0. On this Mac the tested
JDK is Homebrew `openjdk@17`. Set `JAVA_HOME` to your JDK 17 installation and
`ANDROID_HOME` to your Android SDK, or create an ignored `local.properties` with
`sdk.dir=/your/Android/sdk`.

From `Quest/`:

```sh
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease :app:lintDebug
adb devices -l
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.comfygallery.quest/.QuestActivity
```

Windows uses the same project with `gradlew.bat`; no Windows build has been run
yet. Enable Quest Developer Mode and approve USB debugging before installation.
The debug APK uses the local Android debug signing key. The release APK is
unsigned and requires private signing before installation. No signing keys are
checked in.

The scene is created in code. Android Studio and Meta Spatial Editor are optional
for the command-line build. There are no scene-export or custom-shader steps;
the reference sample's NDK requirement does not apply to this app.

## Private connection defaults

Fill in the ignored `Quest/private-connection.properties` file on your computer:

```properties
gallery.url=https://your-gallery.example
gallery.token=your-api-token
```

Use unquoted values. A blank template also lives in
[private-connection.properties.example](private-connection.properties.example).
Rebuild the debug APK after saving the file. The Connect panel then offers
**Connect to my Gallery**, which verifies the supplied pair and saves the login
using Android Keystore. Manual entry remains available. Existing saved logins
continue restoring normally.

These values are embedded in the **private debug APK** and can be extracted from
it; keep that APK private. The local config and generated source/build outputs
are ignored by Git. Release APKs always use empty built-in defaults. Disconnect
clears the saved login; it does not remove values compiled into the APK. Rebuild
with empty config values to remove embedded defaults.

## Decision register

| Decision | Status | Direction |
| --- | --- | --- |
| Quest directory/branch | User confirmed | `Quest/`, `codex/quest-app-planning`. |
| Device/input | User confirmed | Quest 3 and controllers; hand tracking optional. |
| XR design reuse | User confirmed | Reuse hierarchy/behavior; adapt interaction. |
| Spatial player | User confirmed | Optional; ordinary playback works independently. |
| Framework | Implemented, device check pending | Kotlin, Compose, Meta Spatial SDK, Media3. |
| Scene | Provisional implementation | Focused passthrough Library and Viewer. |
| Development host | macOS build verified | Windows remains an alternative. |
| Spatial selection | Proposed | Ordinary default; explicit spatial action when validated. |
| Distribution | Initial scope | Private installation; public store release deferred. |

Pins: Meta SDK 0.14.0, Kotlin 2.1.0, AGP 8.11.1, Gradle 9.4.1, Compose BOM
2024.09.03, Media3 1.4.1 and JDK 17. Android compile SDK is 35, minimum/target
SDK is 34, and declared minimum Horizon OS is 69. These follow the current Meta
sample baseline, not a claim that every dependency is the newest release.

## Boundary and next step

Quest owns this app, Gradle build, tests and client documents. `XR/` remains
visionOS and `mobile/` remains iOS/iPadOS. This implementation changes no backend
or shared spatial representation semantics. Source packages separate data,
Library state, media and UI; the activity owns scene/connection lifetimes.

The debug APK was installed and launched on a USB-connected Quest 3 on 2026-09-17.
Package version 0.1.0 and the resumed app process were confirmed. Continue the
[device checklist](device-validation.md#physical-device-checklist), starting with
controller-only connection entry and ordinary media. The reference sample has
not been installed. Startup does not establish visual or playback acceptance.

The closed [#2](https://github.com/blkot/ProjectComfyGallery/issues/2) contains
Apple spatial-video history; Quest execution uses
[#17](https://github.com/blkot/ProjectComfyGallery/issues/17).

## Attribution

The wrapper and Meta integration patterns come from the public Meta Spatial SDK
samples. The pinned sample commit and retained licenses are recorded in
[licenses](licenses/README.md). No sample environment or private media assets
are included.
