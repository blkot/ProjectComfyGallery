# ADR-0010: Do Not Model ComfyUI Instances

**Status:** Accepted
**Date:** 2026-07-23

## Context

Historical media came from messy tests across ComfyUI versions and node-package combinations. The producing installation often cannot be known. Requiring source roots or media to map to a ComfyUI instance would create false certainty and manual work.

## Decision

- Do not create persistent ComfyUI-instance domain entities.
- Treat configured ComfyUI URLs as operational integration settings.
- Store anonymous, versioned schema snapshots.
- Select historical node definitions by structural compatibility.
- Keep media identity internal and content-based.

## Consequences

- Historical imports do not require unavailable provenance.
- Multiple schema variants can coexist.
- Model/node matches may remain filename-based or ambiguous.
- The system cannot use instance identity to disambiguate same-name historical files and must preserve uncertainty.

## Alternatives considered

- **Named instance profiles mapped to import roots:** rejected because the mapping is often unknowable.
- **Assume the current ComfyUI schema:** rejected because historical versions/packages differ.
