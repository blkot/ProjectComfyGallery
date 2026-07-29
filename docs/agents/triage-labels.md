# Triage and Issue Labels

Every triaged issue must have exactly one category and one triage state. Areas are
multi-select. Priority is single-select when the work is prioritized.

## Matt Pocock triage-state mapping

| Canonical role | GitHub label | Meaning |
| --- | --- | --- |
| `needs-triage` | `state:needs-triage` | Maintainer evaluation is required |
| `needs-info` | `state:needs-info` | Waiting for more information |
| `ready-for-agent` | `state:ready-for-agent` | Fully specified for an agent session |
| `ready-for-human` | `state:ready-for-human` | Requires human action or judgment |
| `wontfix` | `state:wontfix` | Will not be actioned |

When an installed skill mentions a canonical role, apply the mapped `state:*`
label—not an unprefixed label with a similar name.

## Category — exactly one

| Label | Use |
| --- | --- |
| `bug` | Existing behavior is broken |
| `enhancement` | New behavior or an improvement |

Use `documentation` only as an additional descriptive label. It does not replace
the required `bug` or `enhancement` triage category.

## Area — one or more

| Label | Boundary |
| --- | --- |
| `area:backend` | API, database, worker, or shared Python core |
| `area:web` | React web application |
| `area:ios` | Native iPhone/iPad application |
| `area:xr` | Apple Vision Pro/visionOS application |
| `area:infrastructure` | Deployment, CI, storage, networking, or operations |
| `area:documentation` | Product, architecture, API, or development docs |

Apply every area that owns a material part of the outcome. Do not use areas as
workflow states.

## Priority — at most one

| Label | Meaning |
| --- | --- |
| `priority:p0` | Critical and immediately blocking |
| `priority:p1` | High-priority planned work |
| `priority:p2` | Normal-priority planned work |
| `priority:p3` | Low-priority or opportunistic work |

Absence of a priority means it has not been prioritized, not that it is P3.

## Feature and coordination labels

| Label | Meaning |
| --- | --- |
| `feature:spatial-media` | Spatial-image or spatial-video capability |
| `meta:tracking` | Parent issue coordinating work across roles or sessions |
| `blocked` | Cannot progress until a declared dependency resolves |

Every `blocked` issue must name the blocker in its body or latest coordination
comment. Remove `blocked` when the dependency resolves.

## Wayfinder labels

| Label | Meaning |
| --- | --- |
| `wayfinder:map` | Parent investigation map |
| `wayfinder:research` | Primary-source research ticket |
| `wayfinder:prototype` | Throwaway prototype ticket |
| `wayfinder:grilling` | Decision-interview ticket |
| `wayfinder:task` | Implementation or verification ticket |

Wayfinder tickets still require one category, one `state:*` label, relevant areas,
and an optional priority.
