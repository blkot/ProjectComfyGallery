# Native iOS Development Handoff

**Status:** Build plan for an independent iOS engineer or coding agent  
**Recommended toolchain:** Current stable Xcode, Swift 6 language mode, iOS 17+

## Technical direction

Build a native SwiftUI application with no third-party runtime dependencies in the
first milestone.

Use:

- SwiftUI for screens and adaptive layout.
- Observation (`@Observable`) for feature state.
- Structured concurrency and actors for network, command ordering, and caches.
- URLSession for JSON and authenticated media.
- Keychain Services for bearer-token storage.
- SwiftData for the server profile, UI restoration, cached session summaries, and
  pending mutation outbox.
- ImageIO for display-sized image downsampling.
- AVKit/AVFoundation for video playback.
- OSLog for redacted diagnostics and signposts.
- XCTest and XCUITest for unit, integration, and UI coverage.

Avoid adding an architecture framework, networking library, image loader, or
dependency-injection package until a measured need exists.

## Suggested repository layout

The iOS agent may create the Xcode project inside `mobile/`:

```text
mobile/
├─ ComfyGalleryMobile.xcodeproj
├─ ComfyGalleryMobile/
│  ├─ App/
│  │  ├─ ComfyGalleryMobileApp.swift
│  │  ├─ AppEnvironment.swift
│  │  └─ RootView.swift
│  ├─ Core/
│  │  ├─ API/
│  │  │  ├─ APIClient.swift
│  │  │  ├─ APIError.swift
│  │  │  ├─ Endpoint.swift
│  │  │  └─ Models/
│  │  ├─ Auth/
│  │  │  ├─ CredentialStore.swift
│  │  │  └─ ConnectionService.swift
│  │  ├─ Media/
│  │  │  ├─ MediaRepository.swift
│  │  │  ├─ ImageDecoder.swift
│  │  │  └─ VideoCache.swift
│  │  ├─ Persistence/
│  │  │  ├─ LocalStore.swift
│  │  │  └─ PendingMutation.swift
│  │  └─ Support/
│  ├─ Features/
│  │  ├─ Connection/
│  │  ├─ Library/
│  │  ├─ Viewer/
│  │  ├─ ReviewHome/
│  │  ├─ ReviewWorkspace/
│  │  └─ Settings/
│  ├─ DesignSystem/
│  ├─ Resources/
│  └─ PreviewContent/
├─ ComfyGalleryMobileTests/
├─ ComfyGalleryMobileUITests/
└─ Fixtures/
```

Keep API DTOs separate from feature view state. Do not put networking inside SwiftUI
views.

## Architecture

Use a small unidirectional feature pattern:

```text
SwiftUI gesture/action
        ↓
Feature model (@Observable, @MainActor)
        ↓
Repository or command actor
        ↓
APIClient / SwiftData / media cache
        ↓
Authoritative response
        ↓
Feature model replaces rendered state
```

Recommended ownership:

- `AppEnvironment` constructs and owns long-lived services.
- One feature model owns each screen's loading and presentation state.
- `APIClient` is an actor that normalizes URLs, injects bearer auth, performs
  decoding, and maps error envelopes.
- `ReviewCommandQueue` is an actor that serializes commands per evaluation.
- `MediaRepository` is an actor that coordinates memory/disk cache and request
  cancellation.
- SwiftData persists only disposable client state and pending commands; PostgreSQL
  remains authoritative.

Protocols should exist at service boundaries used by tests, not around every type.

## App configuration

Use `.xcconfig` files for non-secret build settings:

```text
Config/
├─ Debug.xcconfig
└─ Release.xcconfig
```

No API token belongs in the project, scheme, source, fixture, or build setting.

Required app metadata:

- `NSLocalNetworkUsageDescription` explaining connection to the user's gallery.
- HTTPS by default.
- A narrowly documented development policy for HTTP LAN servers.

App Transport Security deserves explicit testing. A trusted HTTPS reverse proxy is
the preferred production setup. If raw private-IP HTTP must be supported, use the
smallest practical ATS exception and keep broad arbitrary-load settings out of
release builds intended for wider distribution.

## Connection and credential design

Define one `ServerProfile`:

- stable local UUID;
- normalized base URL;
- optional display name;
- last successful server version;
- last connection date.

Store the token separately in Keychain, keyed by the server-profile UUID. Suggested
accessibility is `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`, unless product
testing shows background access is unnecessary and a stricter setting is practical.

Connection flow:

1. Parse and normalize URL with `URLComponents`.
2. Call `/health/live` without auth.
3. Call `/api/v1/auth/session` with bearer token.
4. Persist profile only after both succeed.
5. On `401`, remove the in-memory credential and present reconnect. Erase Keychain
   only after the user confirms replacement/disconnect.

Never print a token, complete URL with sensitive query, prompt body, or media body.
Use OSLog privacy annotations and redacted errors.

## API client

Implement typed endpoints without generating an entire client in V1. The mobile
surface uses a small subset, and the current OpenAPI document omits bearer security.
Reconsider `swift-openapi-generator` after the backend OpenAPI exposure is corrected.

`APIClient` responsibilities:

- resolve relative API/media paths against one validated base URL;
- reject resolved URLs on a different origin;
- add `Authorization: Bearer`;
- set JSON headers;
- apply connect/resource timeouts;
- decode success before returning;
- decode the structured error envelope for non-2xx responses;
- retain `X-Request-ID` where available;
- support `Data`, download-file, and JSON response modes;
- respect cancellation;
- never retry non-idempotent evaluation commands blindly.

Use `URLSessionConfiguration.waitsForConnectivity = true`. Prefer a dedicated
ephemeral session for authenticated JSON/media requests so credentials and media do
not enter shared URL caches. Application-managed caches provide predictable bounds.

## Domain models

Define only fields the mobile app uses:

- `UserSession`
- `Health`
- `MediaPage` and `MobileMediaSummary`
- `ReviewSummary`
- `ReviewSession`
- `ReviewItem`
- `ReviewMedia`
- `ReviewPrompt`
- `Evaluation`
- `Criterion`
- `EvaluationScore`
- `APIErrorEnvelope`

Use enums with an `unknown(String)` or tolerant custom decoding path for server
states that may expand. Use UUID and Date where decoding is reliable; keep raw
server IDs as strings only if doing so materially simplifies fixture compatibility.

Do not include filename, SHA-256, model, workflow, source, or registry fields in
mobile domain models.

## Authenticated image pipeline

Do not use `AsyncImage`; it cannot reliably express the required authenticated,
bounded, downsampled pipeline.

1. Request preview data through `APIClient`.
2. Verify MIME type and a reasonable response size.
3. Downsample with `CGImageSourceCreateThumbnailAtIndex` to display pixel size times
   screen scale.
4. Cache encoded bytes on disk and decoded images in `NSCache`.
5. Key caches by server profile + media ID + derivative kind.
6. Cancel work when cells disappear and deprioritize prefetch.
7. Purge decoded images on memory warning.

Never use filename as an identity or cache key.

## Authenticated video pipeline

Bearer-protected playback cannot be delegated to a plain unauthenticated `AVPlayer`
URL. For the V1 media sizes and LAN environment:

1. Request `/playback` using authenticated URLSession download.
2. Write the completed file atomically into the bounded video cache.
3. Use the local file URL with `AVPlayerItem`.
4. Keep the poster visible during download.
5. Prefetch only the next review video.
6. Maintain an LRU index and purge on cache limit/storage pressure.
7. Remove partial files after cancellation/failure.

This favors reliability over immediate streaming. If real files make full download
too slow, coordinate a backend signed-URL or supported authenticated streaming
contract rather than relying on private AVFoundation header options.

## Review state and command outbox

### Immediate local interaction

When a score is committed:

1. Create a `PendingMutation` in SwiftData before starting the request.
2. Update the rendered criterion optimistically.
3. Enqueue the command in `ReviewCommandQueue`.
4. Send it with the last authoritative `expected_version`.
5. On success, replace the complete evaluation with the server response.
6. Remove the pending mutation.

Suggested pending fields:

- local UUID;
- server-profile UUID;
- review-session UUID;
- media UUID;
- evaluation UUID;
- criterion-version UUID when applicable;
- command kind: score, N/A, clear, trash, restore;
- intended payload;
- base evaluation version;
- creation date;
- attempt count and last error category.

Do not store prompt or media data in the command outbox.

### Serialization

Use one FIFO lane per evaluation. A response increments the evaluation version, so
the next queued command must be rebased onto that acknowledged version. Coalesce
multiple unsent changes to the same criterion when safe, but never coalesce away a
command already acknowledged by the server because revisions are intentional.

### Retry

- Connectivity and 5xx: bounded exponential backoff with jitter.
- 401/403: stop and require reauthentication.
- 404/422: stop and show actionable error.
- 409 version conflict: stop lane, fetch current review item, and present the
  documented reconciliation UI.

The backend does not currently accept idempotency keys for score commands. If a
network connection drops after the server commits but before the client receives the
response, fetch the current item before replay. If the intended state is already
present, treat the command as reconciled; otherwise surface a conflict instead of
guessing.

## Session and lifecycle restoration

Persist:

- selected tab;
- Library filter and last loaded anchor;
- active review-session ID;
- last visible position;
- pending commands;
- media cache index.

Server `current_cursor` is authoritative after successful PATCH. Local position
allows fast restoration while the server request loads.

On `scenePhase` changes:

- inactive/background: pause prefetch, persist feature state, and allow only a short
  best-effort command flush;
- active: validate auth if stale, reconcile pending commands, fetch the visible
  session/item, then restart next-item prefetch.

Do not mark sessions abandoned or finished from lifecycle events.

## Navigation and score safety

- Next/Previous requests first ensure the current command lane is either acknowledged
  or durably queued locally.
- PATCH the server cursor.
- Update local position.
- Present prefetched content if available.
- Never invoke Next as a side effect of Complete, Trash, Restore, or a score.

Undo records the previous local choice for only the last user action. It sends a
normal versioned command; it is not a server rollback.

## Blind-boundary enforcement

Treat blind review as a testable security-like boundary:

- `ReviewWorkspace` depends only on `ReviewItem`.
- No `MediaDetail` type is imported into the Review feature.
- No media-detail, workflow, model, collection, source, or analysis request may
  originate while Review is active.
- Accessibility labels and error messages use generic media wording.
- Debug overlays for Review must not show IDs or URLs in ordinary builds.
- Snapshot/UI tests scan rendered strings for forbidden fixture values.

The Library API happens to return filenames, but `MobileMediaSummary` must not decode
or display them.

## Testing strategy

### Unit tests

- URL normalization and same-origin relative URL resolution.
- Error-envelope decoding.
- Unknown enum/additive JSON tolerance.
- Score `0` versus Unset versus N/A.
- Per-evaluation command serialization and version rebasing.
- Retry classification and 409 reconciliation.
- Image downsampling target.
- LRU video-cache eviction.
- Keychain isolation by server profile.

### Fixture contract tests

Store sanitized JSON fixtures for:

- image and video review items;
- core and supplemental evaluations;
- Not started, In progress, Complete, and Trash;
- no prompt, several prompts, and long prompt;
- every mutation response;
- structured API errors, especially 401, 409, and 422.

No real private prompt, filename, token, or media belongs in fixtures.

### Integration tests

Run against the Mac-local Docker environment, not the NAS production database:

- connect/authenticate;
- page Library;
- create random and In progress sessions;
- fetch image/video review items;
- set `0`, set N/A, clear, Trash, restore;
- update/resume cursor;
- create a deliberate version conflict;
- download authenticated preview/playback.

Use `uv` for any Python test/setup helper in accordance with repository policy.

### UI tests

- first connection and invalid token;
- Library paging and filter restoration;
- image zoom and video playback;
- Start, Stop, Continue;
- slider, N/A, Clear, Undo;
- no auto-next on Complete or Trash;
- background/foreground with pending change;
- conflict sheet;
- large Dynamic Type and VoiceOver identifiers;
- forbidden metadata absent from Review.

### Manual device matrix

At minimum:

- one smaller supported iPhone;
- one current large iPhone;
- iPhone landscape;
- iPad or iPad simulator;
- light/dark appearance;
- Wi-Fi loss and server restart;
- representative 1024×1536 images and 480×832 videos;
- Low Power Mode and storage-pressure simulation.

## Delivery phases

### M0 — Skeleton and connection

- Xcode project, CI build/test, app environment.
- Server URL + token onboarding.
- Health and authenticated-session validation.
- Keychain and disconnect.

### M1 — Visual Library

- Paginated adaptive grid.
- Authenticated/downsampled images and video posters.
- Minimal filters.
- Immersive image viewer.
- Authenticated cached video playback.

### M2 — Review home and read-only workspace

- Summary and session list.
- Create random/In progress/current-filter session.
- Resume cursor.
- Blind item rendering, prompt, criteria, image/video.
- Next-item prefetch.

### M3 — Durable evaluation

- Score, N/A, Clear, Undo, Trash, Restore.
- Per-evaluation command queue and SwiftData outbox.
- Save-state UI and no-auto-next guarantees.
- Cursor PATCH and explicit Finish.

### M4 — Resilience and polish

- Conflict reconciliation.
- Offline/foreground recovery.
- Accessibility, privacy cover, memory/storage pressure.
- Performance signposts and device validation.
- Complete integration/UI suite.

Do not deploy or distribute M2 as a review tool until M3 durability semantics pass.

## Definition of done

- All product acceptance scenarios pass on a physical iPhone.
- No Review code path or UI exposes forbidden metadata.
- Image and video review both work against the existing backend.
- Every mutation is versioned and conflicts do not overwrite.
- Pending work survives backgrounding and a forced app relaunch.
- Completion and Trash never navigate automatically.
- Stop and resume preserve the exact session cursor.
- Tokens are Keychain-only and absent from logs/fixtures.
- Cache bounds and memory-pressure behavior are verified.
- The Mac-local backend integration suite passes without touching NAS production.
- Build, configuration, installation, and known limitations are documented for the
  next maintainer.

## Questions to resolve only if implementation evidence requires them

These are not blockers for starting:

- Whether the deployment target must support iOS 16.
- Whether the final distribution path is personal signing, TestFlight, or App Store.
- Whether real video sizes justify a signed streaming endpoint.
- Whether one-time username/password device pairing should replace paste-token
  onboarding.
- Whether multiple gallery server profiles are valuable after V1.

