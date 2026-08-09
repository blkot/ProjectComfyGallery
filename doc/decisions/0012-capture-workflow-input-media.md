# ADR-0012: Capture and Deduplicate Workflow Input Media

**Status:** Accepted
**Date:** 2026-08-09

## Context

Generated media can reference input images or videos through embedded ComfyUI
workflow nodes. Those source files may later be renamed, replaced, or deleted,
and the same input is often reused by many workflows and generated media. Reading
the current file directly from ComfyUI at display time would therefore make the
gallery dependent on mutable external storage and an available ComfyUI service.

## Decision

- Preserve every detected workflow input reference, including its workflow node,
  input slot, and original ComfyUI file locator.
- Resolve the reference through the configured ComfyUI API during background
  processing after import. Resolution is best-effort and does not block the media
  record from becoming usable.
- Validate the response, calculate its SHA-256, and copy resolved input image or
  video bytes into immutable managed storage.
- Maintain one workflow input asset for each exact SHA-256 and link every use to
  that shared asset. Repeated uses do not create duplicate stored files.
- Serve captured input media from Comfy Gallery. Do not depend on ComfyUI when
  displaying it later.
- Keep unresolved references and their resolution state so unavailable inputs
  remain visible and can be retried.
- Do not introduce persistent ComfyUI-instance entities. The configured ComfyUI
  URL remains an operational setting under ADR-0010.

## Consequences

- Renaming, replacing, or deleting a ComfyUI input after successful capture does
  not change the input shown for already processed gallery media.
- A shared input asset can be linked to many media records and workflow nodes
  without duplicating its bytes.
- Exact historical input is guaranteed only when capture succeeds. Before that,
  the embedded workflow reference remains the available ground truth.
- Managed input assets participate in storage accounting and backup but are not
  independent gallery media records and do not inherit evaluations, favorites,
  collections, or output-media identity.

## Alternatives considered

- **Proxy from ComfyUI whenever displayed:** rejected because the external file is
  mutable and ComfyUI may be offline.
- **Copy once per generated media:** rejected because inputs are frequently reused
  and would consume duplicate storage.
- **Make each input a gallery media record:** rejected because an input asset is
  supporting provenance, not a generated result to evaluate and organize.
