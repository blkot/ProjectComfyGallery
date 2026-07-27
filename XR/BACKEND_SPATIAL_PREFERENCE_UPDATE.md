# Backend update: persist the preferred spatial-view state

## Goal

Store a small preference on each gallery image so every client can learn whether
that image should open spatially. Do **not** store or export RealityKit's
generated `Spatial3DImage`; visionOS will keep generated objects only in the XR
app's in-memory session cache.

Use this contract everywhere:

```text
spatial_view_preferred: boolean
```

Existing and newly ingested media must default to `false`.

## Backend changes

### 1. Database model and migration

In `packages/py/core/src/comfy_gallery_core/db/models.py`, add a non-null Boolean
column to `Media`:

```python
spatial_view_preferred: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default=false(),
)
```

Import the SQLAlchemy `false` expression if needed.

Create the next Alembic migration under
`packages/py/core/migrations/versions/`, following revision
`0009_media_evaluation_modules`. The upgrade must add
`media.spatial_view_preferred` as non-null with a database-side `false` default
so existing rows are backfilled safely. The downgrade should drop the column.

### 2. Read responses

In `apps/api/src/comfy_gallery_api/media_schemas.py`, add
`spatial_view_preferred: bool` to:

- `MediaListItemResponse`
- `MediaDetailResponse`

In `apps/api/src/comfy_gallery_api/routes/media.py`, populate the field in both
the list-item mapper and the media-detail response. This is an additive API
change; old clients may ignore it.

### 3. Idempotent update endpoint

Add these Pydantic schemas:

```python
class MediaSpatialPreferenceUpdateRequest(BaseModel):
    spatial_view_preferred: bool


class MediaSpatialPreferenceResponse(BaseModel):
    media_id: UUID
    spatial_view_preferred: bool
    updated_at: datetime
```

Add an authenticated route:

```http
PUT /api/v1/media/{media_id}/spatial-preference
Authorization: Bearer <app token>
Content-Type: application/json

{"spatial_view_preferred": true}
```

Use `PrincipalDep`, matching the token-authenticated XR client. Do not require a
browser-only CSRF dependency for this route.

Behavior:

- Return `404 MEDIA_NOT_FOUND` when the media ID does not exist.
- Accept image media only. Return `422 SPATIAL_PREFERENCE_UNSUPPORTED` for other
  media kinds.
- Set the Boolean, commit, refresh, and return the response schema above.
- Treat repeated writes of the same value as successful; `PUT` is deliberately
  idempotent.
- Do not accept generated spatial bytes, a derivative URL, or device-specific
  metadata.

Expected success response:

```json
{
  "media_id": "7c9a47db-a0af-4e9f-9794-22fc55f65ae2",
  "spatial_view_preferred": true,
  "updated_at": "2026-07-27T12:00:00Z"
}
```

## Required tests

Extend `tests/integration/test_media_library.py` (and migration tests, if the
repository has a separate migration suite) to cover:

1. Existing/new media defaults to `false`.
2. Media list and detail responses expose the field.
3. `PUT true` persists and a later `GET` returns `true`.
4. `PUT false` persists, and repeating either value succeeds.
5. An unknown ID returns the normal media-not-found response.
6. Video/audio media is rejected with
   `SPATIAL_PREFERENCE_UNSUPPORTED`.
7. Authentication is required and updating one media row does not affect
   another.

Run the repository's normal checks through `uv`; at minimum:

```bash
uv run pytest tests/integration/test_media_library.py
uv run ruff check packages/py/core apps/api tests/integration/test_media_library.py
```

Also apply the migration to a disposable database with the repository's
standard Alembic command, then verify both upgrade and downgrade.

## Handoff contract for the XR agent

When the backend is deployed, report:

- the migration revision;
- the final endpoint path and example response;
- confirmation that both media list and detail responses include the Boolean;
- test/check results.

The XR follow-up will then:

1. Decode a missing field as `false` during rollout.
2. Keep strong `Spatial3DImage` objects in a bounded in-memory cache keyed by
   profile and media ID, so reopening during the same app session is instant.
3. Write `true` only after generation succeeds and RealityKit presents the
   spatial image.
4. Write `false` when the user explicitly chooses **Disable Spatial**.
5. If the server says `true` but the session cache has no generated object
   (for example after relaunch), regenerate automatically from the original
   cached/downloaded image.
6. Keep the successful local spatial result visible if the preference write
   fails, and retry or show a non-blocking sync warning.

Do not make XR changes as part of this backend update.
