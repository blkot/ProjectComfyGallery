# Mobile API Contract

**Status:** Based on the implemented `0.1.0-rc.9` backend  
**Base URL example:** `http://192.168.50.68:8181`

## Important documentation note

On the current production web port, `/docs`, `/redoc`, and `/openapi.json` fall
through to the frontend application. The backend's internal OpenAPI document is not
currently proxied at those paths, and its custom authentication dependency does not
declare an OpenAPI bearer scheme.

Do not infer that an endpoint is absent from the public Swagger page. The source
files linked from `mobile/README.md` and this contract are authoritative until the
OpenAPI routing/security documentation is corrected.

## Transport and compatibility

- JSON requests use `Content-Type: application/json`.
- Authenticated requests use `Authorization: Bearer <token>`.
- Bearer-authenticated mutable calls do not require `X-CSRF-Token`.
- IDs are UUID strings.
- Dates are ISO 8601.
- Response URLs such as `preview_url` and `playback_url` are relative to the
  configured base URL.
- The client must tolerate unknown additive response fields.
- The client must never log request authorization headers or media/prompt bodies.

## Authentication

### Recommended V1 setup: existing device token

Create a token in the web application with a label such as `iPhone review`, copy it
once, paste it into mobile onboarding, and store it in Keychain.

Validate it:

```http
GET /api/v1/auth/session
Authorization: Bearer cgpat_...
```

Expected success:

```json
{
  "user": {
    "id": "019f...",
    "username": "admin"
  }
}
```

### Optional one-time device pairing

A later onboarding implementation may:

1. `POST /api/v1/auth/login` with username/password.
2. Retain the `cg_session` and readable `cg_csrf` cookies.
3. `POST /api/v1/api-tokens` with `X-CSRF-Token` equal to the CSRF cookie and body
   `{ "label": "iPhone review" }`.
4. Store the returned `token` in Keychain.
5. Log out and erase the entered password and temporary cookies.

Do not persist the password. Token creation is not required for the first build if
the paste-token flow is available.

## Error envelope

Application errors use:

```json
{
  "error": {
    "code": "EVALUATION_VERSION_CONFLICT",
    "message": "The evaluation changed since it was loaded.",
    "details": {},
    "request_id": "..."
  }
}
```

Decode this body for every non-2xx response. Preserve `request_id` in a user-copyable
diagnostic message, but do not include sensitive request content.

Recommended handling:

| Status | Meaning | Mobile behavior |
|---|---|---|
| 401 | Token invalid/revoked | Return to reconnect state |
| 403 | Authorization/CSRF failure | Treat bearer configuration as invalid |
| 404 | Deleted/missing resource | Refresh session/list; do not retry forever |
| 409 | Optimistic-concurrency conflict | Reconcile explicitly |
| 422 | Invalid scope, cursor, or value | Show server message; correct request |
| 429 | Login rate limited | Respect delay; no rapid retry |
| 5xx | Temporary server failure | Keep pending change and retry with backoff |

## Connectivity

```http
GET /health/live
```

No authentication is required. A healthy response includes service version:

```json
{
  "status": "ok",
  "service": "comfy-gallery-api",
  "version": "0.1.0-rc.9",
  "checks": {}
}
```

Health success does not prove authentication; follow it with
`GET /api/v1/auth/session`.

## Library

### List media

```http
GET /api/v1/media?kind=image&evaluation_state=in_progress&trash=false&sort=file_created_desc&limit=48&offset=0
Authorization: Bearer ...
```

Useful query fields:

- `kind=image|video`
- `evaluation_state=not_started|in_progress|complete`
- `trash=true|false`
- `sort=file_created_desc` by default
- `limit=1..200`
- `offset>=0`

The response contains more fields than mobile needs. Define a narrow `Decodable`
model containing:

```json
{
  "items": [
    {
      "id": "019f...",
      "kind": "image",
      "evaluation_state": "in_progress",
      "is_trash": false,
      "preview_url": "/api/v1/media/019f.../preview"
    }
  ],
  "total": 503,
  "limit": 48,
  "offset": 0
}
```

Swift `Decodable` ignores unknown fields, so filenames and file facts need not be
represented in the mobile domain model.

### Media bytes

```http
GET /api/v1/media/{media_id}/preview
GET /api/v1/media/{media_id}/playback
Authorization: Bearer ...
```

Use authenticated `URLSession` requests. Do not put bearer tokens into query
parameters. Images should be downsampled after download. For V1 video, download the
authenticated playback resource to a bounded local cache and give the local file URL
to `AVPlayer`.

The server may return originals when no derivative/proxy exists. Treat MIME type as
evidence; do not infer format from URL path.

## Review summary and sessions

### Summary

```http
GET /api/v1/review/summary
Authorization: Bearer ...
```

```json
{
  "not_started_count": 120,
  "in_progress_count": 18,
  "complete_count": 320,
  "trash_count": 45,
  "active_session_count": 2
}
```

### List sessions

```http
GET /api/v1/review-sessions?limit=25
Authorization: Bearer ...
```

Each response includes:

- `id`
- `name`
- `source_kind`
- `ordering_mode`
- `status`
- `current_cursor`
- `candidate_count`
- `progress_counts`
- `optional_modules`
- `last_opened_at`

Do not render `scope_snapshot` in the mobile UI because it may reveal experiment
configuration.

### Create random unevaluated session

```http
POST /api/v1/review-sessions
Authorization: Bearer ...
Content-Type: application/json

{
  "name": null,
  "source_kind": "random",
  "filter": {
    "evaluation_state": "not_started",
    "trash": false
  },
  "random_limit": 100,
  "ordering_mode": "random",
  "optional_modules": []
}
```

Include `"character"` in `optional_modules` when the user enables that rubric.

### Create global In progress session

```json
{
  "source_kind": "in_progress",
  "random_limit": 100,
  "ordering_mode": "stable",
  "optional_modules": []
}
```

### Create from current Library filter

```json
{
  "source_kind": "filter",
  "filter": {
    "kind": "video",
    "evaluation_state": "not_started",
    "trash": false
  },
  "random_limit": 100,
  "ordering_mode": "random",
  "optional_modules": []
}
```

The server snapshots candidates when the session is created. Later Library changes
do not alter that session.

### Get and update session

```http
GET /api/v1/review-sessions/{session_id}
PATCH /api/v1/review-sessions/{session_id}
Authorization: Bearer ...
```

Update cursor:

```json
{ "current_cursor": 17 }
```

Update status only after explicit user action:

```json
{ "status": "finished" }
```

Stop/background actions do not need to patch status. Deleting a session uses:

```http
DELETE /api/v1/review-sessions/{session_id}
Authorization: Bearer ...
```

Deletion removes session state, not evaluation data.

## Blind review item

```http
GET /api/v1/review-sessions/{session_id}/items/{position}
Authorization: Bearer ...
```

The response is the only permitted source for an active Review screen:

```json
{
  "session": {
    "id": "019f...",
    "current_cursor": 17,
    "candidate_count": 100,
    "progress_counts": {
      "not_started": 60,
      "in_progress": 10,
      "complete": 30,
      "trash": 4
    }
  },
  "position": 17,
  "media": {
    "id": "019f...",
    "kind": "image",
    "preview_url": "/api/v1/media/019f.../preview",
    "playback_url": "/api/v1/media/019f.../playback",
    "width": 1024,
    "height": 1536,
    "duration_seconds": null
  },
  "prompts": [
    {
      "role": "positive",
      "label": "Prompt",
      "text": "Exact extracted text..."
    }
  ],
  "evaluations": [
    {
      "id": "019f...",
      "evaluation_kind": "base",
      "progress_state": "in_progress",
      "is_trash": false,
      "version": 4,
      "criteria": [],
      "scores": []
    }
  ]
}
```

This projection intentionally excludes filenames, checkpoints, LoRAs, workflow
configuration, sources, tags, and collection membership. Do not supplement it with
`GET /api/v1/media/{id}` while the Review screen is active.

## Evaluation commands

Always send the `version` from the most recent authoritative
`EvaluationResponse`.

### Set integer score

```http
PUT /api/v1/evaluations/{evaluation_id}/scores/{criterion_version_id}
Authorization: Bearer ...
Content-Type: application/json

{
  "expected_version": 4,
  "state": "scored",
  "value": 0,
  "na_reason": null
}
```

Valid scores are integers 0 through 10.

### Set N/A

```json
{
  "expected_version": 5,
  "state": "na",
  "value": null,
  "na_reason": null
}
```

### Clear to Unset

```http
DELETE /api/v1/evaluations/{evaluation_id}/scores/{criterion_version_id}
Authorization: Bearer ...
Content-Type: application/json

{
  "expected_version": 6
}
```

The DELETE request intentionally has a JSON body. Construct a `URLRequest` directly;
do not use an abstraction that discards bodies on DELETE.

### Trash and restore

```http
POST /api/v1/evaluations/{evaluation_id}/trash
POST /api/v1/evaluations/{evaluation_id}/restore
Authorization: Bearer ...
Content-Type: application/json

{
  "expected_version": 7
}
```

Each successful mutation returns the entire authoritative `EvaluationResponse`,
including incremented `version`, updated scores, progress state, and Trash state.
Replace the local evaluation rather than patching only one field.

## Command ordering

Commands for one evaluation must be serialized. If a user commits criterion A and
then criterion B:

1. Store A locally.
2. Send A with version N.
3. Replace local evaluation with response version N+1.
4. Send B with version N+1.

Concurrent mutation requests using the same version will conflict. Different media
may be processed independently, but V1 should prioritize a simple per-evaluation
actor/queue.

## Backend capabilities and gaps

The existing backend is sufficient for a mobile MVP using bearer auth and locally
cached video playback.

Known improvements, not blockers:

- Proxy the FastAPI documentation and OpenAPI document through production Nginx.
- Declare bearer authentication in OpenAPI.
- Add scoped/read-review API tokens; current API tokens inherit the user's access.
- Add short-lived signed media URLs or an officially supported streaming-token
  mechanism if local video download becomes too slow for large files.
- Add server idempotency keys to evaluation mutations if long-lived offline command
  replay becomes a common requirement.
- Add a mobile bootstrap endpoint only if measured request count becomes material;
  do not introduce one preemptively.

