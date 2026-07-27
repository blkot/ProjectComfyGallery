# XR API and Media Contract

**Status:** Based on the implemented gallery backend

**Base URL example:** `http://192.168.50.68:8181`

## Transport

- Resolve API-relative paths against one normalized server base URL.
- Authenticated requests use `Authorization: Bearer <token>`.
- Never place a token in query parameters or media URLs.
- JSON uses `Content-Type: application/json`.
- UUIDs identify media; filenames do not.
- Response media URLs are relative and must remain on the configured origin.
- Decode unknown additive fields without failure.
- Retain `X-Request-ID` for redacted diagnostics.

Native URLSession requests are not subject to browser CORS, but App Transport
Security and local-network privacy configuration still apply.

## Connect and authenticate

### Health

```http
GET /health/live
```

No authentication is required.

### Verify token

```http
GET /api/v1/auth/session
Authorization: Bearer cgpat_...
```

Store the base URL in app state and the token in Keychain. V1 assumes the token was
created in the gallery web application and pasted during onboarding.

The current API token is not scoped to read-only media access. A future
`media:read` token scope would reduce authority but is not required to build the
viewer.

## List media

```http
GET /api/v1/media?kind=image&trash=false&sort=file_created_desc&limit=48&offset=0
Authorization: Bearer ...
```

Useful query fields:

- `kind=image|video`
- `favorite=true|false`
- `spatial_view_preferred=true|false`
- `status=ready`
- `trash=true|false`
- `sort=file_created_desc|file_created_asc|imported_desc|imported_asc|filename_asc|filename_desc|size_desc|size_asc`
- `limit=1..200`
- `offset>=0`

The response contains extra metadata. Define a narrow XR DTO:

```json
{
  "items": [
    {
      "id": "019f...",
      "kind": "image",
      "status": "ready",
      "mime_type": "image/png",
      "width": 1024,
      "height": 1536,
      "duration_seconds": null,
      "byte_size": 5242880,
      "is_trash": false,
      "favorite": true,
      "spatial_view_preferred": true,
      "preview_url": "/api/v1/media/019f.../preview"
    }
  ],
  "total": 503,
  "limit": 48,
  "offset": 0
}
```

Do not decode or render filename, hash, model, workflow, or source fields in the XR
product model.

## Navigate within a live gallery view

```http
GET /api/v1/media/{media_id}/navigation?kind=image&trash=false&sort=file_created_desc
Authorization: Bearer ...
```

The filter and sort parameters must match the Library view that opened the card.

```json
{
  "media_id": "019f...",
  "position": 18,
  "total": 503,
  "previous_id": "019f...",
  "previous_position": 17,
  "next_id": "019f...",
  "next_position": 19
}
```

Use this endpoint for Viewer neighbors rather than assuming the currently loaded
offset page contains them.

The population is live. New imports may change `position` and `total`; the current
media UUID remains the stable anchor. Update position only after a fetch or explicit
navigation, never by moving the visible item spontaneously.

## Narrow media detail

```http
GET /api/v1/media/{media_id}
Authorization: Bearer ...
```

The server returns many fields. XR uses:

- `id`
- `kind`
- `status`
- `mime_type`
- `width`
- `height`
- `duration_seconds`
- `byte_size`
- `preview_url`
- `playback_url`
- `original_url`
- `favorite`
- `spatial_view_preferred`
- derivative MIME/size facts when useful for budgeting

Swift `Decodable` ignores unknown fields. Keep forbidden metadata out of the XR DTO
and UI.

## Media resources

```http
GET /api/v1/media/{media_id}/preview
GET /api/v1/media/{media_id}/playback
GET /api/v1/media/{media_id}/original
Authorization: Bearer ...
```

### Preview

Use for grid cells and the first Viewer visual. Download through authenticated
URLSession and downsample to the display target.

### Playback

Use for video. The server may return a browser-compatible proxy or the original when
no proxy exists.

For MVP:

1. Download through authenticated URLSession.
2. Write to a temporary path.
3. Atomically move into the bounded cache.
4. Create `AVPlayerItem` from the local URL.

Do not auto-play prefetched neighbors.

### Original

Use only when an image is selected for Make Spatial or when the preview is
insufficient for full card quality. Store the immutable bytes in a bounded disk
cache. Pass a local URL or `CGImageSource` to RealityKit.

The on-device generated spatial representation is client state. It is not sent back
to `/media/imports` and does not become gallery ground truth.

## Favorite and spatial preferences

```http
PUT /api/v1/media/{media_id}/favorite
Content-Type: application/json

{"favorite": true}
```

```http
PUT /api/v1/media/{media_id}/spatial-preference
Content-Type: application/json

{"spatial_view_preferred": true}
```

XR enforces `spatial_view_preferred => favorite`. Enabling spatial writes Favorite
first and Spatial second. Disabling spatial writes Spatial false first and Favorite
false second. This ordering keeps any partial two-request state valid, and failed
writes remain visible as retryable session intent.

## Error envelope

```json
{
  "error": {
    "code": "MEDIA_NOT_FOUND",
    "message": "The media record was not found.",
    "details": {},
    "request_id": "..."
  }
}
```

Handling:

| Status | XR behavior |
|---|---|
| 401 | Pause loads/playback and open Connect |
| 403 | Treat token as invalid for this action |
| 404 | Show unavailable card; refresh navigation |
| 409 | Refresh current view if server state changed |
| 422 | Correct invalid filter/position request |
| 5xx | Preserve cached content and offer Retry |

Network loss never closes or relocates a scene.

## Pagination and deduplication

The current API uses offset pagination.

Rules:

- Start with `limit=48`, `offset=0`.
- Advance the next request offset by the raw number of records returned, not by the
  number remaining after UUID deduplication.
- Deduplicate the rendered collection by UUID.
- Stop when the server returns fewer than `limit`, unless an explicit refresh later
  reports a larger total.
- Cancel a page request when the Library filter/sort changes.
- Keep existing pages visible when a later page fails.
- Refresh from offset zero only through explicit pull/Refresh or reconnect.

Viewer navigation remains functional independently through the navigation endpoint.

## Cache contract

Cache namespace:

```text
{serverProfileID}/{mediaUUID}/{resourceKind}
```

Resource kinds:

- grid preview;
- viewer preview;
- original image;
- video playback;
- optional generated-scene in-memory entry.

Requirements:

- atomic file writes;
- content/MIME validation;
- LRU access date;
- total byte budget;
- per-resource failure cleanup;
- no token or filename in cache paths;
- purge all data on confirmed disconnect;
- release decoded images/players/generated entities on memory pressure.

Media originals are immutable by gallery identity, so UUID resource keys are stable.
Derivative recipes may change across server releases; clear derivative caches when
the connected server version changes materially or when decoding fails.

## Prefetch policy

### Grid

- At most four concurrent preview requests.
- Prefetch roughly two rows ahead.
- Cancel far-off tasks after rapid scroll.
- Decode at card pixel size.

### Viewer

- One high-priority current-media task.
- One next-neighbor task.
- One lower-priority previous-neighbor task.
- Fetch neighbor navigation IDs before full media.
- Images: preview first; original may prefetch only within disk/network budget.
- Videos: poster first; full playback prefetch only below configured byte budget.
- Spatial depth: never generate in prefetch.

When the user begins dragging toward one neighbor, raise that neighbor's priority and
cancel/deprioritize the opposite expensive load.

## Current backend gaps

None of these block the XR MVP:

- Public Nginx does not expose FastAPI Swagger/OpenAPI correctly.
- OpenAPI does not declare the custom bearer scheme.
- API tokens have no read-only scope.
- Media listing uses offset rather than cursor/snapshot pagination.
- Authenticated playback has no short-lived signed URL.
- Gallery ingestion does not currently support spatial HEIC photos.
- Backend does not store generated RealityKit spatial scenes.

Potential follow-ups must be driven by device measurements. Do not add an XR-specific
bootstrap or 3D-generation backend before evidence requires it.
