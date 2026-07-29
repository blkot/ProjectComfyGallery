# Deployment and Security

**Status:** MVP production deployment implemented; HTTPS remains operator-managed

## Target environment

The current production release is locked as `0.1.0-rc.11`. Future milestone images
use the exact locked version as their registry tag and OCI version label, plus
source-commit and repository labels. Every upstream runtime/build base is pinned
by immutable SHA-256 digest; changing a base digest is an explicit upgrade
operation.

- x86-64 NAS.
- Intel J4125 CPU.
- No CUDA GPU.
- Docker and Docker Compose.
- Local-network access.
- Low request frequency and moderate bandwidth.
- Persistent filesystem storage controlled by the user.

## Compose topology

Expected services:

```text
frontend/web
api
worker
postgres
redis
backup (scheduled or command profile)
```

The frontend is built into and served by an Nginx reverse-proxy container.
Phase 6 implements all six services, including scheduled backup.

## Networks

- Frontend/web exposes the application port to the LAN.
- PostgreSQL and Redis remain on an internal Compose network and are not published to the LAN.
- API may remain internal behind the web proxy or be exposed only when operationally necessary.
- Worker has no inbound public port.
- Outbound access is required only for configured ComfyUI/LoRA Manager synchronization and optional provider metadata.

`compose.development.yaml` runs a distinct Mac-only PostgreSQL/Redis project on
`127.0.0.1:55432` and `127.0.0.1:56379`. Production Compose exposes only the Nginx
web port to the LAN. The API has no production host port; Nginx proxies the
browser's same-origin `/api` and `/health` requests.

## Persistent volumes

Required:

- PostgreSQL data.
- Managed original media.
- Generated derivatives.
- Backup/export destination.

Phase 1 mounts one configurable host media root at `/data` for managed originals,
derivatives, and staging, plus one configurable read-only host import root at
`/imports`. PostgreSQL and Redis retain named volumes. The backup service mounts
`BACKUP_ROOT` at `/backups`; API receives that mount read-only for status reporting.

Configured bind mounts:

- One or more NAS source roots.
- Import roots should be read-only where practical.
- A separate staging area may be used for uploads and atomic placement.

Volume path changes must be supported through configuration and database-relative managed paths.

## Configuration

Configuration is supplied through environment variables and/or a mounted non-secret config file.

Categories:

- Public application URL and listen ports.
- Timezone.
- PostgreSQL/Redis connection settings.
- Managed, derivative, staging, and backup paths.
- Allowed source roots.
- Upload and scan limits.
- Embedded metadata byte, JSON depth/item, and workflow-node limits.
- Worker concurrency by task class.
- ffmpeg/ffprobe paths and proxy recipe.
- Optional ComfyUI/LoRA Manager URL.
- Session/token secrets.
- Backup retention.
- Log level.

The application should fail startup with actionable validation errors for missing required configuration.

Phase 0 Compose requires `POSTGRES_PASSWORD` and `CG_ADMIN_PASSWORD` and refuses
configuration without them. `.env.example` contains non-secret replacement
markers.

`ALPINE_MIRROR` is an optional build-only repository base. It defaults to Alpine's
official CDN and is applied consistently to all runtime-image hardening steps. An
operator may select a geographically closer compatible mirror when the official CDN
is slow; the NAS deployment currently uses `https://mirrors.aliyun.com/alpine` after
an in-container download check.

`CG_IMAGE_NAMESPACE` and `CG_IMAGE_TAG` select the complete immutable image set.
Local source builds default to `project-comfy-gallery` and the locked source
version. Milestone deployment sets the namespace to
`ghcr.io/blkot/project-comfy-gallery` and uses the exact `VERSION` value. API and
worker deliberately share one backend image.

GitHub Actions authenticates to GHCR with repository-scoped `GITHUB_TOKEN` package
write access. The NAS uses a separately supplied classic personal access token
limited to `read:packages`; the token belongs to Docker credential storage and
MUST NOT enter application `.env` or Git.

## Resource profile

Initial conservative defaults:

- API processes: one or a small fixed count.
- General worker concurrency: low and configurable.
- Video transcode concurrency: one.
- Bounded image-decoding concurrency.
- Streaming hashes and uploads.
- PostgreSQL pool sized for a small deployment.
- Redis memory policy that does not make it authoritative.

Phase 1 starts one Dramatiq worker process with one thread. This deliberately
bounds hashing, image decoding, and video transcode to one heavy operation at a
time on the J4125. Later measured tuning must keep video transcode concurrency at
one unless the NAS evidence supports a change.

Phase 6 retained one process/one thread after a real 1,036-path J4125 scan.
Configurable default container ceilings:

- PostgreSQL: 1 GB and 1.5 CPU.
- Redis: 256 MB and 0.5 CPU, with a 192 MB `noeviction` ceiling.
- API: 768 MB and 1 CPU.
- Worker: 2 GB and 3 CPU.
- Backup: 256 MB and 0.5 CPU.
- Web: 128 MB and 0.5 CPU.

These are ceilings, not reservations. JSON logs rotate at 10 MB × three files per
container by default.

Limits:

- Per-upload and per-batch limits are configurable.
- Worker checks free space before original placement and proxy generation.
- Large raw workflow JSON is not loaded into gallery list responses.
- Phase 2 defaults decoded metadata to 64 MiB, JSON nesting to 128 levels,
  JSON complexity to 250,000 items, and either representation to 20,000 nodes.
  These limits are configurable through the documented `CG_WORKFLOW_*` variables.
- Phase 3 defaults external registry responses to 64 MiB, node snapshots to 20,000
  definitions, metadata fetch concurrency to four, and HTTP operations to a
  180-second timeout. `CG_REGISTRY_*` settings bound each value; metadata concurrency
  cannot exceed eight.

`CG_COMFYUI_BASE_URL` is optional. When present it supplies the default manual-sync
target; a request may also provide a URL for that run. The value is operational
configuration and is never persisted as a ComfyUI-instance entity.

## Intel media acceleration

Hardware video acceleration through `/dev/dri` is a **Deferred optimization**.

Rules:

- Capability-detect rather than assume.
- CPU ffmpeg fallback is mandatory.
- A hardware path must produce equivalent proxy metadata and quality expectations.
- Failure to initialize hardware decoding/encoding retries with safe CPU behavior when configured.

The CPU path met the MVP responsiveness gate on the real J4125; the release does not
require a device mount or hardware-specific ffmpeg recipe.

## Database migrations and upgrades

Upgrade sequence:

1. Confirm a recent backup exists.
2. Pull the intended immutable application version.
3. Run migration preflight.
4. Apply Alembic migrations once.
5. Start API/worker compatible with the migrated schema.
6. Run readiness checks.
7. Verify login, media query, job processing, and evaluation query.

Requirements:

- Migrations are non-interactive.
- Migrations never require ComfyUI, LoRA Manager, or Civitai.
- Long data migrations are resumable or explicitly maintenance-mode operations.
- Downgrade support is evaluated per migration; restore-from-backup is the guaranteed recovery path.

## Authentication design

### Administrator password

- Stored with a modern adaptive password hash such as Argon2id.
- Never logged.
- Bootstrap/setup avoids a permanent default password.
- Login attempts receive basic rate limiting.

Phase 6 implements a per-client, in-process failed-login window. Nginx overwrites
`X-Forwarded-For` with the direct LAN client address so callers cannot supply an
arbitrary forwarding chain to evade it.

### Sessions

- Secure random server-side or signed/rotatable sessions.
- HttpOnly and SameSite cookies.
- `Secure` cookie when HTTPS is used.
- CSRF protection on state-changing cookie-authenticated requests.
- Explicit logout and expiration.

### API tokens

- High-entropy random values.
- Only a hash is stored.
- Token shown once at creation.
- Independently labeled and revocable.
- Authentication failures do not reveal whether a token ID exists.

## LAN threat model

A LAN is not treated as fully trusted. Risks include:

- Another device reading private prompts/media.
- Cross-site requests against an authenticated browser.
- Untrusted prompt/workflow text attempting XSS.
- Malicious filenames or path traversal.
- Corrupt media exploiting decoders.
- Exposed Redis/PostgreSQL.
- Compromised custom ComfyUI extension responses.
- Overly broad source-root mounts.

## Security controls

### Filesystem

- Resolve and validate every source path beneath an allowed root.
- Never accept arbitrary host paths from ordinary API requests.
- Avoid running containers as root where image/runtime support permits.
- Separate read-only import roots from writable managed storage.
- Use restrictive file permissions for secrets/backups.
- Avoid following symlinks outside source roots.

### Untrusted metadata

- Treat prompt, workflow JSON, node descriptions, provider fields, filenames, and paths as untrusted.
- Render text through framework escaping; never inject HTML.
- Bound JSON size/depth and parsing resources.
- Store raw evidence without executing code.
- Do not import/execute custom node Python.

### Media

- Use maintained media libraries/ffmpeg packages.
- Apply decoding time/resource limits.
- Serve safe `Content-Type` and `Content-Disposition`.
- Use authenticated media endpoints.
- Apply range-request validation.
- Do not serve arbitrary files by client-supplied path.

### External integrations

- Validate configured URLs and timeouts.
- Use server-to-server calls.
- Bound response size and parse defensively.
- Persist raw response provenance.
- Do not allow an extension response to overwrite manual registry fields automatically.
- No synchronization endpoint may execute workflows.

### Database and broker

- Internal networking only.
- Strong generated passwords.
- Parameterized queries/ORM.
- Redis is not exposed or trusted as durable storage.
- Database backups avoid leaking credentials in command logs.

## HTTPS

HTTPS on the LAN is **Proposed** through the user’s NAS reverse proxy. The application must function behind a reverse proxy and correctly honor configured trusted proxy headers. Plain HTTP may be allowed in a consciously trusted LAN deployment, but cookie security behavior must be documented.

When the NAS reverse proxy terminates HTTPS, set `CG_SESSION_COOKIE_SECURE=true`,
serve only the HTTPS origin, and set `CG_ALLOWED_ORIGINS` to that exact origin.

## Secrets

- Production secrets are supplied through environment/file secrets, not committed.
- `.env.example` contains placeholders only.
- Secret rotation is documented.
- Backup archives may contain sensitive prompts, metadata, and password hashes and must receive equivalent protection.

## Security verification

Before release:

- Path traversal tests.
- Authentication/session/token tests.
- CSRF tests.
- XSS tests using malicious prompt/workflow strings.
- Unauthorized media-range request tests.
- File-type spoofing tests.
- Oversized/malformed JSON tests.
- Dependency and container image scanning.
- Restore authorization verification.

Phase 6 also adds `no-new-privileges`, CSP/clickjacking/MIME/referrer/permissions
headers, authenticated export downloads with path containment, checksum-verified
guarded restore, and secret-free portable-export regression coverage.

Run the repeatable dependency and amd64 image gates before an upgrade or release:

```bash
make audit
make image-audit
```

`image-audit` builds the final API/worker, web, backup, PostgreSQL, and Redis
artifacts, scans saved archives with Trivy, and fails on any high or critical
finding. Temporary archives and scan-only image tags are removed when the command
exits. The derived PostgreSQL image replaces its vulnerable embedded `gosu` binary
with Alpine `su-exec`; the official entrypoint behavior is otherwise retained. The
2026-07-24 Phase 6 release gate reported zero high or critical findings in all five
runtime artifacts.
