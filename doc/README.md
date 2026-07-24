# Project Comfy Gallery Documentation

## Purpose

This directory is the project’s durable source of product and engineering context. It exists to prevent implementation from drifting away from the use cases and decisions established during discovery.

The documentation follows a structure commonly used in medium-to-large software projects:

1. **Product** — vision, requirements, scope, and user workflows.
2. **Architecture** — system boundaries, data ownership, and cross-cutting design.
3. **Design** — detailed subsystem behavior and invariants.
4. **Interfaces** — APIs and external integrations.
5. **Operations** — deployment, security, backup, recovery, and observability.
6. **Development** — repository organization, testing, fixtures, and delivery plan.
7. **ADRs** — immutable records explaining important architectural decisions.
8. **Governance** — glossary, open questions, and requirements traceability.

This structure borrows the audience separation of the Diátaxis documentation model while retaining product requirements and Architecture Decision Records (ADRs), which are necessary for a long-lived software project.

## Document map

### Product

- [Vision and principles](product/vision.md)
- [Requirements](product/requirements.md)
- [MVP scope](product/mvp-scope.md)
- [User workflows](product/user-workflows.md)

### Architecture

- [System overview](architecture/system-overview.md)
- [Data model](architecture/data-model.md)

### Subsystem design

- [Media ingestion and processing](design/media-ingestion.md)
- [Workflow intelligence and node registry](design/workflow-intelligence.md)
- [Model registry](design/model-registry.md)
- [Manual evaluation](design/evaluation.md)
- [Analytics](design/analytics.md)
- [Frontend UX](design/frontend-ux.md)

### Interfaces and integrations

- [API and integrations](interfaces/api-and-integrations.md)
- [ComfyUI custom-node upload integration](interfaces/comfyui-custom-node-upload.md)

### Operations

- [Deployment and security](operations/deployment-and-security.md)
- [Backup, recovery, and observability](operations/backup-recovery-observability.md)
- [Upgrade runbook](operations/upgrade-runbook.md)

### Development

- [Engineering plan](development/engineering-plan.md)
- [Phase 0 foundation and verification](development/phase-0-foundation.md)
- [Phase 1 media ingestion and verification](development/phase-1-media-ingestion.md)
- [Phase 2 workflow evidence and verification](development/phase-2-workflow-evidence.md)
- [Phase 3 node/model registries and verification](development/phase-3-node-model-registries.md)
- [Phase 4 manual evaluation and review](development/phase-4-manual-evaluation.md)
- [Phase 5 model-focused analytics](development/phase-5-model-analytics.md)
- [Phase 6 NAS release](development/phase-6-nas-release.md)
- [Testing and golden corpus](development/testing-and-golden-corpus.md)

### Decisions and governance

- [Architecture Decision Records](decisions/README.md)
- [Requirements traceability](requirements-traceability.md)
- [Glossary](glossary.md)
- [Open questions](open-questions.md)

## Decision status vocabulary

Every material statement should be distinguishable as one of:

- **Accepted** — explicitly agreed and authoritative for implementation.
- **Proposed** — recommended but not yet explicitly accepted.
- **Deferred** — intentionally outside the current scope.
- **Open** — unresolved and must not be guessed if it changes behavior materially.
- **Superseded** — retained for history but replaced by a later ADR or requirement.

Unless marked otherwise, requirements and design statements in this documentation are **Accepted**.

## Normative language

- **MUST** and **MUST NOT** define required behavior.
- **SHOULD** and **SHOULD NOT** define strong defaults that may be changed only with documented justification.
- **MAY** defines optional behavior.

## Documentation governance

Any change that affects product behavior MUST update:

1. The applicable requirement or subsystem document.
2. The requirements traceability table.
3. An ADR if the change alters an architectural boundary, data invariant, or major technology choice.
4. Tests or acceptance criteria that demonstrate the change.

Implementation work is not complete when behavior changes but its governing documentation remains stale.

ADRs are append-only. A decision is changed by adding a new ADR that supersedes the old one, not by rewriting history.

## Review checklist

Before merging a feature:

- The feature maps to at least one requirement ID.
- User-visible states and failure paths are documented.
- Data migrations preserve existing evaluations and raw workflow metadata.
- The implementation does not introduce a deferred feature accidentally.
- Security, backup, and low-resource NAS behavior were considered.
- Relevant golden-corpus fixtures and tests were updated.
