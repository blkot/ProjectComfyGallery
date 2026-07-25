# iOS App Design — Project Comfy Gallery Mobile

**Date:** 2026-07-26
**Status:** Approved
**Target:** Native iPhone app with adaptive iPad layouts
**Stack:** Swift 6, SwiftUI, async/await, URLSession, AVKit, SwiftData
**Minimum:** iOS 17

## Architecture

Unidirectional feature pattern:

```
SwiftUI gesture/action
  → Feature model (@Observable, @MainActor)
    → Repository or command actor
      → APIClient / SwiftData / media cache
        → Authoritative response
          → Feature model replaces rendered state
```

### Key actors

- `APIClient` — URL resolution, bearer auth injection, JSON/data/download decoding, error mapping, ephemeral URLSession
- `MediaRepository` — coordinates memory/disk cache and request cancellation
- `ReviewCommandQueue` — serializes commands per evaluation, rebases versions after each response, coalesces unsent changes

### Ownership

- `AppEnvironment` constructs and owns long-lived services
- One `@Observable` feature model per screen
- SwiftData persists disposable client state only; PostgreSQL is authoritative
- Protocols exist at service boundaries used by tests, not around every type

## Project structure

```
mobile/
├─ ComfyGalleryMobile.xcodeproj
├─ Config/Debug.xcconfig, Release.xcconfig
├─ ComfyGalleryMobile/
│  ├─ App/          — @main, AppEnvironment, RootView (TabView)
│  ├─ Core/
│  │  ├─ API/       — APIClient, APIError, Endpoint, DTO Models
│  │  ├─ Auth/      — CredentialStore (Keychain), ConnectionService
│  │  ├─ Media/     — MediaRepository, ImageDecoder, VideoCache
│  │  ├─ Persistence/ — LocalStore, PendingMutation (SwiftData)
│  │  └─ Support/   — OSLog helpers, redacted errors
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

## Data models

Domain DTOs (narrow Decodable, unknown field tolerant, enums use `unknown(String)` fallback):
Health, UserSession, MediaPage, MobileMediaSummary, ReviewSummary, ReviewSession,
ReviewItem, ReviewMedia, ReviewPrompt, Evaluation, Criterion, EvaluationScore,
APIErrorEnvelope

No filename, SHA-256, model, workflow, source, or registry fields in mobile models.

## API endpoints

- `GET /health/live` (no auth)
- `GET /api/v1/auth/session`
- `GET /api/v1/media` (paginated, filtered)
- `GET /api/v1/media/{id}/preview` (data), `/playback` (download)
- `GET /api/v1/review/summary`
- `GET/POST /api/v1/review-sessions`, `GET/PATCH/DELETE /api/v1/review-sessions/{id}`
- `GET /api/v1/review-sessions/{id}/items/{position}`
- `PUT/DELETE /api/v1/evaluations/{id}/scores/{cvid}`
- `POST /api/v1/evaluations/{id}/trash|restore`

Error handling: 401→reconnect, 403→invalid config, 404→refresh, 409→reconcile UI, 422→show message, 5xx→backoff retry.

## Features

### Connection
URL normalize → `/health/live` → paste token → `/auth/session` → persist profile + Keychain. HTTP shows LAN warning. Disconnect erases Keychain, cache, pending commands, profile.

### Library
LazyVGrid adaptive columns, 2:3 cells, aspect-fill previews, video glyph, trash veil, progress dot. Filters: kind, progress, trash. Paginated with prefetch. Per-filter scroll position.

### Viewer
Full-screen modal: image zoom/pan, video with native controls. Auto-hide chrome. No metadata drawer.

### Review Home
Continue card (priority), Resume In progress, Start random, recent sessions list. New session sheet: source, max items (1–2000, default 100), ordering, Character rubric.

### Review Workspace
Fixed header (Stop, position/total, save state), fixed media stage (~48-56% height), scrollable prompts + criteria, fixed nav bar (Previous, Undo, Next). Criteria: 0–10 slider, Clear, N/A. Haptic on commit. Trash/Restore toggle. Save states: Saved, Saving…, Saved locally, Needs attention. Conflict sheet: Use server value / Reapply my value. No auto-navigation on Complete/Trash.

### Settings
Connection management, privacy cover toggle, cache size + clear.

## Data flow

Score command: optimistic UI → PendingMutation in SwiftData → enqueue in ReviewCommandQueue → send with expected_version → success replaces evaluation + removes pending → failure triggers retry/reconnect/reconcile.

ReviewCommandQueue: one FIFO lane per evaluation, coalesce unsent same-criterion changes, never coalesce acknowledged commands, rebase version after each response.

## Persistence

SwiftData models: ServerProfile, PendingMutation, CachedSessionSummary. Keychain for bearer tokens (keyed by profile UUID, `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`). Media: 1 GiB bounded disk cache, NSCache for decoded images, LRU video eviction.

## Lifecycle

- `.inactive/.background`: pause prefetch, persist state, bounded command flush
- `.active`: validate auth, reconcile pending, fetch visible item, restart prefetch
- Never mark sessions finished from lifecycle events

## Testing

- Unit: URL resolution, error decoding, enum tolerance, score semantics, command serialization, retry classification, image downsampling, LRU eviction, Keychain isolation
- Fixture: sanitized JSON for all states, mutations, and error codes
- Integration: against local Docker — connect, authenticate, library, sessions, scoring, cursor, conflict, media download
- UI: connection flow, library paging, viewer, review workspace, conflict sheet, Dynamic Type, VoiceOver, forbidden metadata scan
- Manual: small/large iPhone, iPad, landscape, light/dark, network loss, Low Power Mode

## Blind-boundary enforcement

- ReviewWorkspace depends only on ReviewItem
- No MediaDetail imported into Review feature
- No config-revealing requests originate while Review is active
- Accessibility labels use generic wording ("Image under review")
- UI tests scan rendered strings for forbidden fixture values

## Delivery phases

- M0: Skeleton, connection, auth, Keychain, disconnect
- M1: Library grid, image/video viewer, authenticated media pipeline
- M2: Review home, read-only workspace, prompts, criteria display, prefetch
- M3: Scoring, N/A, Clear, Undo, Trash, Restore, command queue, SwiftData outbox, cursor PATCH
- M4: Conflict reconciliation, offline recovery, accessibility, privacy cover, performance signposts, full test suite
