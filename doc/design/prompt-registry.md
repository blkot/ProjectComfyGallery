# Prompt registry and Prompt ID resolution

## Purpose

Xanta Utils' `XantaPromptLibrary` emits a human-facing identifier from its
second output. ComfyGallery treats that value as a stable library reference in
the form `source - index`, while keeping the original string unchanged in
workflow evidence.

The Gallery registry is intentionally separate from workflow evidence. A
registry entry describes the reusable prompt definition; a media match is
derived from the trusted Prompt ID in that media's workflow. Registering,
renaming, or enriching an entry therefore never rewrites a PNG, a workflow
snapshot, or an evaluation.

## Identifier rules

- The separator is the final hyphen before a numeric suffix, so sources may
  contain hyphens: `sfw-zimage-por-v3 - 03786`.
- Whitespace around the separator is normalized for comparison.
- Leading zeroes are preserved for display and round-tripping.
- Source comparison is case-insensitive; the registry keeps the first display
  spelling supplied by the operator.
- A value that does not match this shape remains an opaque Prompt ID and is not
  assigned to a registry entry.

## Evidence precedence

For Prompt ID and Character LoRA display fields:

1. Explicit `comfy_gallery_display_v1` values written by the saver.
2. Verified execution output stored by historical recovery.
3. The visual workflow's `widgets_values` for the bound ShowText node.
4. The API graph's `text_0` widget cache as a last-resort candidate.

The API graph remains authoritative for node classes, links, and execution
topology. Its cached `text_0` is not authoritative for dynamic prompt-library
text because it can predate the execution that produced the image.

## Registry record

Each entry stores:

- `source` and the zero-padded `index` from the Prompt ID;
- positive and optional negative prompt text;
- optional character LoRA and structured LoRA list;
- source metadata and origin (`xanta-utils` by default).

The first implementation exposes authenticated list, lookup, create, update, and
bulk upsert/import API operations. Lookup also returns every media whose trusted
Prompt ID resolves to the requested source/index, including IDs that have not
been registered yet.
This makes stale or incomplete Xanta libraries discoverable without inventing a
prompt definition.

The frontend provides a Prompt Registry page under **System → Prompt Registry**.
Prompt IDs in Media Detail are links to that page, where the definition and all
matching media can be inspected.

## Import shape for a future Xanta Utils adapter

The registry API intentionally accepts a neutral record shape so an adapter can
translate whichever file format a local Xanta Utils installation uses:

```json
{
  "source": "sfw-zimage-por-v3",
  "index": "03786",
  "prompt": "...",
  "negative_prompt": "...",
  "character_lora": "...",
  "lora_list": [],
  "metadata": {}
}
```

No ComfyUI connection is required to browse or resolve existing registry data.
