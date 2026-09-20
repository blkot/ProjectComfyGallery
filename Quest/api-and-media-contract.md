# Quest API and media contract

**Status:** First client implementation, 2026-09-17. Desktop contract checks pass;
live Gallery and physical media tests remain in [device validation](device-validation.md).

## Sources of truth

- [Media routes](../apps/api/src/comfy_gallery_api/routes/media.py)
- [Media schemas](../apps/api/src/comfy_gallery_api/media_schemas.py)
- [Authentication](../apps/api/src/comfy_gallery_api/routes/auth.py)
- [Variant routes](../apps/api/src/comfy_gallery_api/routes/variants.py)
- [Committed OpenAPI](../doc/interfaces/openapi.json)
- [Client API changelog](../doc/interfaces/client-api-changelog.md)

The [XR contract](../XR/api-and-media-contract.md) supplies behavioral precedent.
Its Swift APIs, full-download strategy, image-generation commands, and
spatial-first video defaults are not automatically Quest requirements.

## Connection and transport

Use one normalized gallery base URL. Preserve its configured path prefix when
resolving server resource paths. Authenticated requests use an
`Authorization: Bearer ...` header, including image and video byte requests.
Never embed tokens in URLs or logs. Validate resource and redirect destinations
against the configured origin before attaching credentials.

Plan protected credential storage backed by Android Keystore; keep nonsecret
profile settings separate. Disconnect cancels requests, releases the player, and
removes credentials. Namespace caches by profile and resource identity so
switching servers cannot expose the previous profile's media.

The existing LAN deployment may use HTTP. Q2 must configure and verify Android
network policy for that explicit user-selected server and handle local-network
requirements for the chosen OS/target SDK. Do not bypass TLS validation for HTTPS.
No connection address or token is hard-coded into the shipping app.

## Endpoint inventory

| Purpose | Request | Client responsibility |
| --- | --- | --- |
| Reachability | `GET /health/live` | Separate an unreachable server from rejected authentication. |
| Verify token | `GET /api/v1/auth/session` | Treat rejection as a connection state, not empty Library. |
| Library | `GET /api/v1/media` | Send filter/sort/offset/limit; ignore unknown additive fields. |
| Detail | `GET /api/v1/media/{id}` | Obtain media facts and server-provided resource URLs. |
| Navigation | `GET /api/v1/media/{id}/navigation` | Use the Viewer scope; resolve playable neighbors. |
| Preview | List/detail `preview_url` | Authenticated grid/poster image. |
| Ordinary video | Detail `playback_url` | Original or proxy; never infer stereo from this route. |
| Full image | Detail `original_url` when needed | Bounded transfer and display-sized decode. |
| Favorite | `PUT /api/v1/media/{id}/favorite` | Body `{"favorite": true}` or `false`; reconcile the result. |
| Optional variant | Ready variant `content_url` | Request only after representation capability checks. |

Only Favorite is a core media mutation. Conversion submission, variant import,
delete/Trash, and shared playback-preference writes are outside this plan.

## Library and navigation rules

Initial query: `trash=false`, `sort=file_created_desc`, `limit=48`, `offset=0`.
Images/Videos adds `kind=image|video`; All omits it. Favorite-only adds
`favorite=true`; normal browsing omits it. Oldest order uses `file_created_asc`.

The current API accepts one exact `status` value. Omit it and allow only `ready`
and `ready_with_warnings` locally. Advance the next raw offset by the server page's
raw item count, not the visible or deduplicated count. Continue through fully
filtered pages until a visible page or server exhaustion; support cancellation
and bounded batches with an explicit continuation rather than infinite fetching.
Use a scope generation to discard late responses after filters/refresh change.

Viewer scope captures filter/sort semantics, not a frozen ID list. Resolve
Previous/Next through the navigation endpoint, inspect candidate detail, and skip
unplayable candidates in the same direction. Use a visited-ID/progress guard and
cancellable bounded traversal. Missing/removed anchors trigger reconciliation
and a return-to-Library path rather than guessing from filenames or offsets.

Backend positions/totals refer to the raw live scope and may include records
hidden by the local status policy. Do not label them as exact playable counts.
Imports and Favorite changes can alter that scope; they must not spontaneously
change visible media. If unfavoriting removes the Viewer anchor from a
Favorite-only scope, retain its content, reconcile Library, and reset navigation
to a clear out-of-scope state until the user selects another item.

## Narrow client models

- `ServerProfile`: normalized URL and credential reference.
- `GalleryScope`: kind, Favorite-only, order, hidden-Trash policy, local generation.
- `MediaSummary`: ID, kind, status, dimensions, duration, preview URL, Favorite,
  availability, and optional preference facts.
- `MediaDetail`: summary facts, original/playback URLs, MIME/size and variants.
- `MediaVariant`: ID, role, status, MIME/container/codec/dimensions/size, content URL.
- `MediaNavigation`: current ID and server positions plus neighbor IDs.
- `PlaybackSelection`: media ID, representation, resource identity, generation,
  time position, and play intent.

Unknown variants are ignored. Unknown media kinds/statuses are not playable.
Do not expand DTOs into workflow/model/evaluation data just because those fields
exist in a response.

## Media loading and lifecycle

Prototype authenticated Media3 streaming with HTTP ranges and seeking. If a
bounded download/cache path is required for a representation, record the reason
and size policy rather than silently downloading an entire large library.
Keep current playback ahead of thumbnail/prefetch work. Prefetch immediate
neighbors with bounded concurrency; never start their video decoders or audio.

One active player session owns its surface and callbacks. Every selection change
advances a generation. Late load/seek/end-of-item/error/teardown callbacks cannot
affect a newer generation. Pause on inactivity; release on close/disconnect.
Test end-of-item versus Loop/sequence arbitration and seek completion races.

On 401, cancel authenticated work and request reconnection; do not cycle through
media as though files failed. On a missing variant, refetch detail once and
fallback to ordinary content. Keep other retries explicit and bounded.

## Optional spatial selection

`spatial_available` means the backend has an active ready Apple spatial video;
it is not a Quest decoder capability. A video MIME type or generic HEVC codec
string also does not establish two-eye support.

Use an explicit user action plus a tested capability policy, availability, and
a ready `role=spatial_video` with nonempty `content_url`. Select the supplied URL,
not a fabricated variant path. Inconsistency or failure uses ordinary playback
and leaves server fields untouched. Legitimately silent variants do not require
synthesized audio; embedded audio must work when present.

The present contract admits Apple MV-HEVC, not SBS under the same role. If SBS is
needed, first design a separate shared representation/validation change that
allows both formats to coexist. The optional Quest feature cannot overwrite the
working Vision Pro variant. [ADR-0011](../doc/decisions/0011-imported-media-variants.md)

## Contract verification

Q2/Q3 tests use sanitized representative payloads: additive/unknown fields,
unplayable-only pages, repeated IDs, cancellation, missing anchors, and 401s.
Q4 device evidence covers actual media requests, ranges/seeking, audio, memory,
and lifecycle. Optional Q6 covers direct Gallery MV-HEVC files and real stereo
presentation. Store fixtures/results without private tokens or media bytes.
