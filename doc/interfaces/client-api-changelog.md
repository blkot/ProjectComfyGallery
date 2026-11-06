# Client API Changelog

This file is the cross-agent handoff for backend contract changes. Consumers should
also use the committed [OpenAPI snapshot](openapi.json); prose here explains
semantics and compatibility that a schema alone cannot express.

## Unreleased: Library slideshow start window

`GET /api/v1/media/slideshow` adds optional `start_media_id=<uuid>`. The server
locates that media in the same filtered/collection scope and complete requested
sort order, including existing tie-breakers, before applying the playlist limit.
The chosen media is therefore the first item even if it lies beyond the first
2,000 results. The window contains it and subsequent items only, with no
wraparound. A missing or out-of-scope start returns `404 MEDIA_NOT_IN_VIEW`.

When combined with `shuffle=true`, the start remains pinned first and the rest
of the bounded window is shuffled using the existing random-seed contract.
Requests without `start_media_id` retain their previous behavior. Response
`total` remains the size of the whole matching scope; `truncated` is true when
any scope records are omitted, including those before the requested start.
Clients must include the start ID in their playlist request/cache key, rather
than locating it only within the first returned 2,000 items.

## Unreleased: context-preserving Prompt Usage browsing

**Database migration:** none.

```http
GET /api/v1/prompt-registry/lookup?prompt_id=<id>&group_by_character=true&preferred_character_lora=<name>
GET /api/v1/prompt-registry/usage/navigation?prompt_id=<id>&media_id=<uuid>&preferred_character_lora=<name>
GET /api/v1/prompt-registry/usage/slideshow?prompt_id=<id>&start_media_id=<uuid>&preferred_character_lora=<name>&limit=2000
```

- Lookup (including `GET /prompt-registry/{entry_id}`) adds optional
  `group_by_character=false` and `preferred_character_lora` parameters. The
  existing default remains `created_at DESC, id DESC`. Grouped lookup, Usage
  navigation, and Usage slideshow all share the same deterministic order:
  preferred character first, remaining character names alphabetically using
  trimmed/lowercase keys, undefined character last, then
  `created_at DESC, id DESC` inside each group. Clients must retain server order
  rather than re-sorting groups with a different locale comparator.
- `preferred_character_lora` changes ordering only; it does not discard any
  media. All three routes also accept the existing `character_lora` **filter**,
  matched case-insensitively with surrounding whitespace ignored. Prompt ID
  parsing and numeric-index equivalence are unchanged.
- Scope is the exact Prompt Usage history, including non-favorites and Trash,
  not the broader Library or favorite-only heatmap count. Usage still works
  when the Prompt ID has not been registered. Registration is needed for prompt
  text, not for media navigation.
- Navigation returns the existing `MediaNavigationResponse`: one-based
  `position` and `total`, plus neighboring IDs/positions or `null` at boundaries.
  A current media outside the prompt/character scope returns
  `404 MEDIA_NOT_IN_VIEW`; invalid Prompt IDs return `422 PROMPT_ID_INVALID`.
- Slideshow returns the existing `SlideshowPlaylistResponse`, with preview and
  raw playback routes for each media. `limit` defaults to 2,000 and must be
  between 1 and 2,000. `start_media_id`, when provided, is the first playlist
  item; the limit is applied **after** locating it, even when it lies beyond the
  initial playlist window. Out-of-scope starts return `404 MEDIA_NOT_IN_VIEW`.
  There is no wraparound: only the requested media and following items are
  returned. `total` is the whole matching scope; `truncated` indicates that the
  response omits any scope records (including records before the requested
  start). `shuffle` is false and `random_seed` is null; clients may shuffle the
  returned playlist. An empty scope without a requested start returns `items: []`.

The indexed path performs counting, ordering, pagination, and navigation in SQL,
without loading workflow graphs. The existing trusted-evidence fallback is
retained for installations whose materialized Prompt ID index is incomplete.

## Unreleased: Prompt Registry character-LoRA filter

**Database migration:** `0021_prompt_index_character_lora`

`media_prompt_index` now materializes the declared `character_lora` display value
(from the saver packet or a verified historical recovery row). Read additions:

```http
GET /api/v1/prompt-registry/character-loras?q=<substring>&limit=50
GET /api/v1/prompt-registry/heatmap?character_lora=<name>
GET /api/v1/prompt-registry/random?character_lora=<name>
GET /api/v1/prompt-registry/stats?character_lora=<name>
GET /api/v1/prompt-registry/lookup?prompt_id=<id>&character_lora=<name>
```

`character-loras` returns `{name, media_count}` entries for distinct values that
currently have media, ordered by media count. Every filter combines `source` and
`character_lora` with AND semantics and matches the character name
case-insensitively; entries without a character value never match the filter.
For `random` and `stats`, `character_lora` scopes the favorite signal rather than
the candidate universe: `unmaterialized` means no favorited, non-trashed media
with that character, so a prompt never generated with the character remains a
candidate. `registered_count` in `stats` stays the full source universe. `lookup`
returns only matching media and adjusts `total_media`. Existing rows are backfilled
by `rebuild-prompt-index`; workflows that do not declare a character LoRA remain
unrepresented in character-scoped counts.

## Unreleased: favorite-scoped prompt materialization

Prompt materialization now follows the Favorite signal instead of raw generation
history. An entry is **materialized** when at least one linked media record is
favorited and not in Trash. Trash outranks Favorite: a trashed favorite does not
materialize its prompt, and neither does media that was never favorited.

- `GET /api/v1/prompt-registry/random?materialization=unmaterialized` now returns
  entries that have no favorited, non-trashed media. Its `media_count` counts the
  same favorite scope.
- `GET /api/v1/prompt-registry/stats` uses the same definition for
  `materialized_count` and `unmaterialized_count`.
- `GET /api/v1/prompt-registry/neighbor` reports the favorite-scoped
  `media_count`.
- `GET /api/v1/prompt-registry/heatmap` defaults to favorites outside Trash and
  accepts `include_not_faved=true` and `include_trash=true`. `max_media_count`
  follows the requested scope.
- `GET /api/v1/prompt-registry/lookup` keeps complete generation history and now
  marks each media record with `is_trash`; `total_media` is unchanged.

Clients that relied on "trash still counts as generated" must switch to the
explicit heatmap flags to see that history.

## Unreleased: prompt registry read APIs

**Database migration:** `0020_prompt_registry_index_key`

Prompt registry entries now keep a canonical numeric index key so padded Prompt IDs
resolve consistently for materialization checks. Authenticated clients can use:

```http
GET /api/v1/prompt-registry/sources?q=<prefix>&limit=24
GET /api/v1/prompt-registry/heatmap?source=<source>&include_not_faved=false&include_trash=false&limit=20000&offset=0
GET /api/v1/prompt-registry/random?source=<source>&materialization=<state>
GET /api/v1/prompt-registry/stats?source=<source>
GET /api/v1/prompt-registry/neighbor?source=<source>&index=<index>&direction=<previous|next>
```

Random selection returns `PROMPT_REGISTRY_RANDOM_NOT_FOUND` when the filters have
no candidates. Read routes accept the existing web session or Bearer API token,
while registry write routes keep their existing CSRF or API-token requirements.

The heatmap response is optimized for a compact client-rendered contribution
matrix. It returns `items[]` with `prompt_id`, `source`, `index`, and
`media_count`, plus `total`, `limit`, `offset`, and `max_media_count`.

## Unreleased: media content-safety ratings

**Database migrations:** `0015_media_content_rating`, `0022_media_rating_default_sfw`

Every media record now carries a non-null `content_rating` value: `sfw` or
`nsfw`. Migration `0022_media_rating_default_sfw` backfills historical `null`
rows to `sfw` and adds the same server default for new records. SFW is the
implicit baseline and is not shown as a card badge; an NSFW record is shown with
the compact `R` badge. The list and detail projections expose the effective value.
The list, navigation, slideshow, saved-filter, selection, and review scope
queries still accept `content_rating=sfw|nsfw`; the legacy `unknown` query value
is retained as a compatibility alias for `sfw` during the transition.

```http
PUT /api/v1/media/{media_id}/content-rating
POST /api/v1/media/bulk/content-rating
```

The single-media command accepts `{"content_rating":"sfw"}` or
`{"content_rating":"nsfw"}`. The bulk command accepts the same membership
scope used by favorite/trash actions and the same two values. There is no clear
operation: returning a record to the baseline means explicitly setting `sfw`.

## Unreleased: ComfyGallery-driven MSS spatial conversion

**Database migration:** `0013_spatial_conversion_runs`

**Event-driven update:** `0014_event_driven_mss` completes the
short submission Job after MSS batch persistence. `refresh` provides an on-demand
single status GET; `retry-publish` asks MSS to publish an existing result without
regenerating it. A ready/duplicate CG variant activation is the success authority.

Media Detail and other authenticated clients can now start and observe an MSS
conversion without contacting MSS directly:

```http
POST /api/v1/media/{media_id}/spatial-conversions
GET  /api/v1/media/{media_id}/spatial-conversions/current
GET  /api/v1/spatial-conversions/{run_id}
```

The POST accepts optional `precision`, `spatial_quality`, and `spatial_preset`
JSON strings and returns `{configured, conversion, job}` with `202`. It reuses an
active run for the same media. The current endpoint returns the latest historical
run or null fields when none exists, so clients can restore state after navigation
or restart. Poll while status is `queued`, `submitting`, or `processing`; on
`succeeded`, re-fetch media detail and its active `variants` projection.

The browser must never call MSS or persist its token/base URL. `configured=false`
means the server operator has not set `CG_MSS_BASE_URL`. Conversion failures do
not remove the ordinary original or an existing ready spatial variant. Manual
variant upload remains compatible and available as a separate recovery path.

## Unreleased: captured workflow input media

**Database migration:** `0012_workflow_input_media`

Media clients can now read workflow input provenance separately from the large
workflow graph:

```http
GET /api/v1/media/{media_id}/workflow-inputs
GET /api/v1/media/{media_id}/workflow-inputs/{input_id}/content
POST /api/v1/media/{media_id}/workflow-inputs/resolve
```

The list returns one item per detected workflow node/input locator. `status=ready`
items include immutable SHA-256 asset facts and `content_url`; non-ready items keep
their original ComfyUI reference plus a stable error code. Clients must use the
returned content URL and must not call ComfyUI directly.

The resolve command is asynchronous and returns `{media_id, job}`. It accepts a
browser session with CSRF or a bearer API token. Missing or unreachable input files
are per-reference outcomes, so the capture job can succeed after recording them;
call the resolve command again to retry those references after ComfyUI or its files
become available.

Captured assets are shared globally by exact SHA-256 bytes. They are provenance
objects, not gallery media records: they have no evaluation, favorite, collection,
or navigation state.

After deploying the migration, existing media can be discovered and queued through
`POST /api/v1/workflows/reprocess` with `{"mode":"all"}`. New imports schedule
capture automatically after workflow extraction.

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
