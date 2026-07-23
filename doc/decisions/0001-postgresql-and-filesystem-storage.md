# ADR-0001: PostgreSQL and Filesystem Storage

**Status:** Accepted
**Date:** 2026-07-23

## Context

The application manages structured identities, mutable/correctable registries, versioned evaluations, jobs, and analytical snapshots alongside potentially many gigabytes of immutable media. Workflow shapes vary and require flexible raw storage, but relationships and migrations remain important.

## Decision

- Use PostgreSQL as the authoritative metadata database.
- Use relational tables for identities, relationships, state, and versioning.
- Use JSONB for heterogeneous raw/derived payloads where normalization would lose flexibility.
- Store original media and derivatives on mounted filesystem volumes.
- Use Alembic for schema migrations.

## Consequences

- Strong transactions and constraints protect manual work.
- JSONB supports varied custom-node data without abandoning relational queries.
- Media backup and database backup are separate operational concerns.
- Deployment includes PostgreSQL rather than a single embedded database file.

## Alternatives considered

- **SQLite:** simpler deployment but weaker fit for concurrent API/worker writes, durable jobs, and larger analytical queries.
- **Store media in PostgreSQL:** simpler transactional ownership but poor operational fit for large immutable files and NAS backup.
- **Document database only:** flexible workflow payloads but weaker relational integrity for evaluations, revisions, and registries.
