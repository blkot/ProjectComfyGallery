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
- `prefer_spatial_playback=true|false`
- `spatial_available=true|false`
- `status=ready`
- `trash=true|false`
- `sort=file_created_desc|file_created_asc|imported_desc|imported_asc|filename_asc|filename_desc|size_desc|size_asc`
- `limit=1..200`
- `offset>=0`

The XR **Spatial** saved view filters user intent with
`prefer_spatial_playback=true`; it is not an availability-only view. Availability
may be shown separately for video.

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
      "spatial_available": false,
      "prefer_spatial_playback": true,
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
- `spatial_available`
- `prefer_spatial_playback`
- active ready `variants[]` with `id`, `role`, `status`, `mime_type`,
  `byte_size`, and `content_url`
- derivative MIME/size facts when useful for budgeting

Swift `Decodable` ignores unknown fields. Keep forbidden metadata out of the XR DTO
and UI. During the backend compatibility window, the client may decode deprecated
`spatial_view_preferred` only when canonical `prefer_spatial_playback` is absent.

## Media resources

```http
GET /api/v1/media/{media_id}/preview
GET /api/v1/media/{media_id}/playback
GET /api/v1/media/{media_id}/original
GET /api/v1/media/{media_id}/variants/{variant_id}/content
Authorization: Bearer ...
```

### Preview

Use for grid cells and the first Viewer visual. Download through authenticated
URLSession and downsample to the display target.

### Playback

Ordinary `playback_url` may return a browser-compatible proxy or the original when
no proxy exists. It never switches to MV-HEVC automatically.

The detail response's `variants[]` contains active ready variants only. For a
video, select its source with this fail-safe rule:

```text
prefer_spatial_playback
&& spatial_available
&& variants contains role=spatial_video, status=ready, nonempty content_url
    -> selected variant content_url
otherwise
    -> ordinary playback_url
```

Do not construct a variant URL. Ignore unknown roles and use the server-provided
`content_url`. If the availability projection and variant list ever disagree, the
ordinary source wins. Preserve a true user preference across this fallback so a
later valid replacement becomes eligible again.

For MVP:

1. Download the selected path through authenticated URLSession.
2. Validate a `video/*` response.
3. Write to a temporary path.
4. Atomically move into the bounded cache.
5. Keep `video/quicktime` as `.mov`.
6. Create `AVPlayerItem` from the local URL and present it with
   `AVPlayerViewController`.
7. Configure recommended AVKit experiences. For a stored spatial-video source,
   transition to `.expanded` and wait for completion before playing; for an
   ordinary source, reconcile to `.embedded`.
8. When the preference changes, replace the current item in the existing
   `AVPlayer`; do not destroy the player/controller or reset Loop.

Do not auto-play prefetched neighbors.

The variant content endpoint supports HTTP byte ranges for a future authenticated
AVFoundation streaming loader. The first implementation performs an authenticated
full download; it does not place the bearer token in the URL or use undocumented
asset-header options.

### Original

Use only when an image is selected for Make Spatial or when the preview is
insufficient for full card quality. Store the immutable bytes in a bounded disk
cache. Pass a local URL or `CGImageSource` to RealityKit.

The on-device generated spatial representation is client state. It is not sent back
to `/media/imports` and does not become gallery ground truth.

## Favorite and playback preferences

```http
PUT /api/v1/media/{media_id}/favorite
Content-Type: application/json

{"favorite": true}
```

```http
PUT /api/v1/media/{media_id}/playback-preference
Content-Type: application/json

{"prefer_spatial_playback": true}
```

`favorite`, `prefer_spatial_playback`, and `spatial_available` are independently
stored:

- Favorite is user-owned and changes only through `/favorite`.
- Playback preference is user-owned, applies to both images and videos, and changes
  only through `/playback-preference`.
- Spatial availability is read-only system state for stored video variants; it is
  false for runtime spatial images.
- Importing, replacing, invalidating, or removing a video variant changes neither
  user preference nor Favorite.

One XR image interaction intentionally writes both independent user fields:

- successful Make Spatial or Enable Cached Spatial writes Favorite `true` and
  playback preference `true`;
- Disable Spatial writes Favorite `false` and playback preference `false`;
- Favorite remains independently editable between those image actions;
- spatial-video Play Spatial / Play in 2D writes only playback preference and never
  changes Favorite.

The client optimistically retains failed preference writes as retryable session
intent, but it must write only the field or fields defined by the interaction. The
deprecated `/spatial-preference` route and `spatial_view_preferred` payload remain
backend compatibility aliases and are not used by current XR code.

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
ordinary resource:
    {serverProfileID}/{mediaUUID}/{resourceKind}

stored spatial video:
    {serverProfileID}/{mediaUUID}/spatial-video-playback/{variantUUID}
```

Resource kinds:

- grid preview;
- viewer preview;
- original image;
- ordinary video playback;
- stored spatial-video playback;
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
Spatial variants are replaceable, so their UUID is part of both the cache index key
and local filename. A new active variant can never reuse bytes from its predecessor.
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
- Videos: poster first; prefetch the currently selected representation only when
  that source's own `byte_size` is below the configured budget.
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
