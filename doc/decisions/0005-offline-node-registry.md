# ADR-0005: Offline Node Registry with Optional ComfyUI Enrichment

**Status:** Accepted
**Date:** 2026-07-23

## Context

ComfyUI `/object_info` provides useful current node schemas, but historical nodes may be deleted or changed and ComfyUI may be offline. The user expects the application to perform first-pass classification and only require corrections.

## Decision

- Persist versioned node definitions and semantic mappings locally.
- Accept optional anonymous ComfyUI schema snapshots.
- Key variants by class/module/schema fingerprint.
- Automatically activate confirmed and high-confidence mappings.
- Keep ambiguous suggestions out of analysis until reviewed.
- Provide an unknown-node inbox and persistent manual corrections.
- Defer a full visual rule editor.

## Consequences

- Import and review remain available offline.
- Current ComfyUI data significantly reduces manual work.
- Historical schema ambiguity remains explicit.
- The application owns an inference/confidence system and reprocessing workflow.

## Alternatives considered

- **Require live ComfyUI:** rejected because historical/messy installations cannot be identified reliably.
- **Manual registry only:** rejected because the initial workload would be unacceptable.
- **Heuristics only:** rejected because current node schemas and graph types provide stronger evidence.
