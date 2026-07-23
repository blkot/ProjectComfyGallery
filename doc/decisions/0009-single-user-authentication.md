# ADR-0009: Single-User Authentication

**Status:** Accepted
**Date:** 2026-07-23

## Context

The system is self-hosted on a LAN but exposes private media, prompts, workflows, and filesystem-derived information. Multi-user collaboration is not required.

## Decision

- Provide one administrator login.
- Use authenticated browser sessions.
- Provide separately revocable bearer tokens for machine clients.
- Do not build roles, registration, invitations, or multi-user permissions in MVP.

## Consequences

- LAN access is protected without a large identity system.
- Authorization logic stays simple.
- Future multi-user work would require a new ADR and data-model changes.
- API tokens support later custom-node integration.

## Alternatives considered

- **No authentication:** rejected because LAN devices should not automatically access private data.
- **Full RBAC:** rejected as unnecessary MVP complexity.
- **Shared static password on every request:** rejected because sessions and revocable tokens are safer and more usable.
