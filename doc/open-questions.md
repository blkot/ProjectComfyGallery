# Open Questions

This file contains unresolved decisions only. Resolved items must move into requirements/design and, when material, an ADR.

## Product and naming

- **OPEN-001:** Confirm the permanent product name; “Project Comfy Gallery” is currently a working name.

## Infrastructure

- **OPEN-005:** Determine whether the NAS Docker runtime exposes Intel media acceleration through `/dev/dri`. CPU transcoding remains the required fallback.
- **OPEN-006:** Confirm production volume paths, backup destination, timezone, and exposed port during deployment.
## Deferred integrations

- **OPEN-010:** Define authentication scopes and idempotency retention for the future
  ComfyUI custom-node ingestion API when that deferred integration is scheduled.
- **OPEN-011:** Define whether future Hugging Face enrichment is hash-, repository-, or manual-link driven.
