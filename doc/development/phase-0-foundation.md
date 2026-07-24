# Phase 0 Foundation and Verification

**Status:** Implemented
**Implementation version:** `0.1.0-rc.6`
**Last verified:** 2026-07-23

## Purpose

Phase 0 establishes a production-shaped foundation before media ingestion is
added. It intentionally contains no placeholder media, parser, evaluation, or
analytics records. Those domains begin as vertical slices in later phases.

## Implemented runtime

| Component | Implementation | Responsibility |
|---|---|---|
| Web | React 19, TypeScript, Vite, Nginx | Login, foundation dashboard, API-token lifecycle |
| API | FastAPI | Authenticated HTTP boundary, health and system status |
| Worker | Dramatiq | Separate bounded background process and test actor |
| Database | PostgreSQL 17 | Authoritative users, sessions, and API-token records |
| Broker | Redis 8 | Non-authoritative Dramatiq transport |
| Migrations | Alembic | Transactional schema baseline |

Nginx is the only service exposed to the LAN by default. It serves the SPA and
proxies `/api` and `/health` to the internal API. PostgreSQL and Redis are
published only on `127.0.0.1` to support local host-based development and are
not reachable from other LAN devices.

## Repository map

| Path | Ownership |
|---|---|
| `apps/api` | FastAPI application, dependencies, routes, schemas, stable errors |
| `apps/worker` | Dramatiq broker and actors |
| `apps/web` | React application and browser tests |
| `packages/py/core` | Settings, auth services, security, ORM, Alembic |
| `tests` | Python unit, API, and integration tests |
| `deploy/docker` | Backend/web images, Nginx, API startup sequence |
| `compose.yaml` | Local and NAS runtime topology |
| `.github/workflows/ci.yml` | Python, web, migration, and Compose gates |

## Startup contract

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` and `CG_ADMIN_PASSWORD`.
3. Run `docker compose up --build`.
4. Open port `8080` on the NAS and log in with `CG_ADMIN_USERNAME`.

Compose refuses to resolve when either required password is absent. API startup
applies Alembic migrations, creates the administrator only when missing, and
then starts Uvicorn. The worker and web services wait for API readiness.

The administrator password is Argon2-hashed. Browser sessions and CSRF material
are high-entropy values stored only as SHA-256 hashes in PostgreSQL. API tokens
are shown once, stored only by hash, retained after revocation for audit, and
rejected after revocation.

## Verification record

The following passed on 2026-07-23:

| Gate | Result |
|---|---|
| Ruff lint and formatting | Pass |
| mypy strict mode | Pass, 23 source files |
| pytest | Pass, 7 tests |
| ESLint and strict TypeScript | Pass |
| Vitest | Pass, 3 tests |
| Vite production build | Pass with route-level chunks |
| Compose configuration validation | Pass |
| Empty PostgreSQL migration | Pass |
| Alembic schema-drift check | Pass |
| Full five-service Compose startup | Pass |
| API/worker/web health | Pass |
| Browser login and protected navigation | Pass |
| CSRF negative case | Expected `403` |
| API-token create, bearer use, revoke | Pass |
| Nginx SPA/API proxy | Pass |
| Browser console warnings/errors | None |
| Backend `linux/amd64` image build | Pass |
| Web `linux/amd64` image build | Pass |

## Commands

```bash
make bootstrap
make check
make migrate
docker compose up --build
docker compose ps
docker compose logs -f
```

For an explicit target-architecture build check:

```bash
docker buildx build --platform linux/amd64 \
  --file deploy/docker/backend.Dockerfile \
  --tag comfy-gallery-backend:amd64-check --load .

docker buildx build --platform linux/amd64 \
  --file deploy/docker/web.Dockerfile \
  --tag comfy-gallery-web:amd64-check --load .
```

## Intentionally not implemented

- Media tables, managed storage, import volumes, and scanning.
- Durable job records and retry reconciliation.
- ComfyUI workflow extraction and node/model registries.
- Evaluation criteria, review sessions, and analytics.
- Backup/export jobs and retention.
- Direct ComfyUI custom-node ingestion.

These omissions are phase boundaries, not unstated behavior. Phase 1 begins with
the media identity and ingestion vertical slice described in the
[engineering plan](engineering-plan.md).
