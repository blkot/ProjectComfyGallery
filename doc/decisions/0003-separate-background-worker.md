# ADR-0003: Separate Durable Background Worker

**Status:** Accepted
**Date:** 2026-07-23

**Amended:** 2026-08-03

## Context

Hashing, scanning, metadata extraction, image decoding, video probing/transcoding, registry synchronization, and analysis can block HTTP handling. The NAS has a low-power J4125 CPU, and imports may contain thousands of files.

## Decision

- Run FastAPI and background work as separate services.
- Use Dramatiq with Redis as the message transport.
- Keep authoritative job/stage state in PostgreSQL.
- Bound concurrency by work type, especially one video transcode by default.
- Isolate `system`/`media` in a critical one-thread worker pool and run `scan`,
  `workflow`, `registry`, and `maintenance` in a separate one-thread pool.
- Give the pools separate heartbeat paths so the API's critical-worker readiness
  signal cannot be overwritten by background-worker lifecycle events.
- Make stages idempotent and retryable.

## Consequences

- API responsiveness is isolated from heavy work.
- Redis loss does not erase authoritative business state.
- Compose includes more services and requires job reconciliation.
- Long maintenance and registry work cannot starve imports or variant validation.
- Work can resume after process restarts.

## Alternatives considered

- **FastAPI background tasks:** insufficient durability and isolation.
- **One combined process:** simpler but vulnerable to CPU-heavy stalls and restarts.
- **PostgreSQL-only job queue:** possible, but Dramatiq/Redis provides mature worker transport while PostgreSQL remains authoritative.
