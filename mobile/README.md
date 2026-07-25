# Project Comfy Gallery Mobile

**Status:** Handoff specification  
**Target:** Native iPhone application with adaptive iPad layouts  
**Recommended stack:** Swift 6, SwiftUI, async/await, URLSession, AVKit, SwiftData  
**Minimum deployment target:** iOS 17

## Purpose

The mobile application is a focused companion to Project Comfy Gallery. It connects
to the existing self-hosted backend and supports two activities:

1. Visually browse and play managed images and videos.
2. Perform fast, configuration-blind manual review that can stop and resume at any
   time.

The application is deliberately not a mobile administration console. It does not
show filenames, hashes, workflow graphs, checkpoint names, LoRA names, sampler
configuration, source paths, analytics, registry controls, import controls, or
operational dashboards.

Exact extracted prompts remain visible during review because the established rubric
is configuration-blind and prompt-aware. Prompts are review evidence, not experiment
configuration.

## Platform decision

Native SwiftUI is the recommended implementation.

- SwiftUI provides adaptive iPhone/iPad layouts, Dynamic Type, VoiceOver semantics,
  state restoration, and system navigation without a third-party UI runtime.
- AVKit provides the most reliable iOS video playback behavior.
- URLSession, Keychain, ImageIO, and SwiftData cover the network, security, image
  memory, and resumability requirements.
- The product is a compact, media-heavy client with no need to share a cross-platform
  codebase. A web wrapper would add authentication, caching, video, and gesture
  compromises without reducing meaningful scope.

If support for iOS 16 becomes necessary, replace SwiftData with Core Data and the
Observation framework with `ObservableObject`; the product and API contracts do not
otherwise change.

## Handoff documents

Read these documents in order:

1. [Product requirements](product-requirements.md) — scope, invariants, and acceptance
   criteria.
2. [UI/UX design](ui-ux-design.md) — information architecture, screens, interaction,
   adaptive layouts, and accessibility.
3. [API contract](api-contract.md) — current backend endpoints, payloads,
   authentication, concurrency, and known gaps.
4. [Development handoff](development-handoff.md) — Swift architecture, media
   pipeline, persistence, testing, and delivery phases.

The existing server remains authoritative:

- [`doc/design/evaluation.md`](../doc/design/evaluation.md)
- [`doc/interfaces/api-and-integrations.md`](../doc/interfaces/api-and-integrations.md)
- [`apps/api/src/comfy_gallery_api/routes/evaluations.py`](../apps/api/src/comfy_gallery_api/routes/evaluations.py)
- [`apps/api/src/comfy_gallery_api/evaluation_schemas.py`](../apps/api/src/comfy_gallery_api/evaluation_schemas.py)

If this handoff conflicts with server behavior, preserve data and blind-review
invariants first, record the mismatch, and correct the contract rather than inventing
client-only semantics.

## Locked decisions

- iPhone-first native SwiftUI application; iPad is adaptive, not a separate product.
- One active gallery server profile in V1.
- Browse and review only; no import, metadata inspection, registry, analytics, or
  administration.
- Review uses server-side review sessions and the blind review-item response.
- Review displays exact prompts but no configuration-revealing metadata.
- Every criterion is Unset, N/A, or an integer from 0 through 10.
- Zero is a real score.
- Completing or trashing media never moves to the next item automatically.
- Navigation is explicit.
- Score changes save independently and preserve optimistic-concurrency versions.
- A user may leave after any item and resume the same server-side cursor.
- Local pending writes survive ordinary app suspension and short network loss.
- Bearer credentials live only in Keychain and are never logged.
- The backend database remains authoritative; mobile caches are disposable.

## Definition of the first useful build

The first useful build can:

- connect to a configured LAN gallery;
- authenticate with a device API token;
- show a smooth visual image/video library without metadata;
- create or resume a blind review session;
- display exact prompts and all applicable evaluation criteria;
- score, clear, mark N/A, undo, trash, restore, and explicitly navigate;
- survive backgrounding and resume at the same position;
- handle a stale evaluation version without overwriting server data;
- play authenticated videos from a bounded local cache; and
- pass the blind-boundary, image, video, interruption, and accessibility tests in
  the development handoff.

