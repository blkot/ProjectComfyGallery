# Client API Changelog

This file is the cross-agent handoff for backend contract changes. Consumers should
also use the committed [OpenAPI snapshot](openapi.json); prose here explains
semantics and compatibility that a schema alone cannot express.

## Unreleased: import result discovery

**Database migration:** none

Ordinary upload-batch responses now expose explicit follow-up links:

```json
{
  "id": "<batch-id>",
  "status_url": "/api/v1/imports/<batch-id>",
  "items": [
    {
      "id": "<upload-item-id>",
      "media_id": null,
      "media_url": null,
      "variant_import_url": null
    }
  ]
}
```

`POST /api/v1/media/imports` remains asynchronous. Its top-level `id` is an
import-batch ID, not a media ID. Poll `status_url` until the item is `completed`,
`duplicate`, or `failed`. Completed and duplicate items contain the resolved
`media_id`, `media_url`, and `variant_import_url`; processing and failed items do
not invent media links.

To attach a spatial-video variant, fetch `media_url` after resolution, copy its
`sha256` as `source_asset_sha256`, then submit the variant to
`variant_import_url`. Existing clients that use only `id` and `media_id` remain
compatible.

## Unreleased: library keyword search

**Database migration:** none

`GET /api/v1/media`, `GET /api/v1/media/{media_id}/navigation`, and
`GET /api/v1/media/slideshow` now accept optional `q` text with a maximum length of
256 characters. Search is case-insensitive and partial. Leading and trailing
whitespace is ignored; blank input behaves as no search filter.

Search covers current checkpoint and LoRA raw/normalized references, confirmed
alias display names, resolved artifact display/file names, current successfully
extracted positive/negative prompts, and original or attached-variant SHA-256 hashes.
Fields use OR; `q` combines with all other filters using AND. Totals, pagination,
sorting, navigation, and slideshow scope all resolve from the same matching
population.

The same endpoints accept `sha256=<64-character-hex-sha256>` for a case-insensitive
exact match against the original asset hash or any stored attached-variant hash.
`sha256` combines with `q` and all other filters using AND. `MediaFilterRequest`
also carries `sha256`, so saved filters, server-filtered collection/tag membership,
selection scopes, and review sessions can preserve an exact hash lookup.

Reusable `MediaFilterRequest` expressions now include `q`, so saved filters,
server-filtered collection/tag membership, selection scopes, and review sessions can
preserve the same query. Prompt search intentionally excludes stale, superseded,
failed, or unclassified observations.

## Unreleased: spatial-video variants

**Database migration:** `0011_spatial_video_variants`

### Duplicate retry semantics

- Variant-import status now has a terminal `duplicate` value. It means a new
  command submitted bytes that were already the active, ready variant for the same
  media and role; the associated job succeeds and no second managed file is
  created.
- `validation_data.duplicate_of_variant_id` identifies the preserved active
  variant. Clients should present this as already attached, refresh media detail,
  and must not offer a validation retry.
- Historical `failed` imports with `VARIANT_DUPLICATE_CONFLICT` remain valid audit
  records. Exact bytes owned by another media still produce that conflict.

### Additive media fields

List and detail media projections now return:

```json
{
  "spatial_available": false,
  "prefer_spatial_playback": true,
  "spatial_view_preferred": true
}
```

- `spatial_available` is read-only and true only for an active ready stored
  `spatial_video` variant. It is false for images.
- `prefer_spatial_playback` is user intent for images and videos.
- `spatial_view_preferred` is a deprecated response alias with the exact same value.
- `favorite` remains independent.

Detail responses add `variants`, containing only active ready rows. Use each row's
`content_url`; do not construct or request managed paths.

### Canonical preference command

```http
PUT /api/v1/media/{media_id}/playback-preference
Content-Type: application/json

{"prefer_spatial_playback": true}
```

The legacy `/spatial-preference` command remains available, now works for videos,
and updates the same backing value.

### Filters

Media list, navigation, saved-filter, collection/tag membership, and review scopes
accept:

```text
prefer_spatial_playback=true|false
spatial_available=true|false
```

The deprecated `spatial_view_preferred` filter is accepted. Sending it together
with the canonical name is valid only when their values agree.

### External converter import

```http
POST /api/v1/media/{media_id}/variant-imports
Authorization: Bearer <token>
Idempotency-Key: <stable command key>
Content-Type: multipart/form-data
```

Multipart fields:

```text
file
role=spatial_video
source_asset_sha256=<original media sha256>
converter_name=<optional>
converter_version=<optional>
```

Success is `202` with `{variant, job}`. Poll
`GET /api/v1/jobs/{job_id}` or
`GET /api/v1/media/{media_id}/variant-imports/{variant_id}`. A job succeeds only
after fail-closed content validation, managed storage, and atomic activation.

### Variant delivery

```http
GET /api/v1/media/{media_id}/variants/{variant_id}/content
Range: bytes=...
```

Only the active ready variant is readable. The endpoint supports byte ranges for
AVFoundation. Existing `playback_url`, `preview_url`, and `original_url` retain
their old ordinary-media behavior.

### Required client actions

- Main React web: use canonical preference/filter fields; keep ordinary video
  playback; display preference and availability separately.
- Mobile: the blind-review projection is unchanged; no required playback change.
- XR: choose `variants[].content_url` only when video preference and availability
  are both true; otherwise use ordinary `playback_url`.
- External converter: send the original asset SHA-256 and a stable idempotency key;
  never send a NAS path.
