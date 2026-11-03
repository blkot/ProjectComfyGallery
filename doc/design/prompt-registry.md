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

For Prompt ID and related workflow display fields:

1. Explicit `comfy_gallery_display_v1` values written by the saver.
2. Verified execution output stored by historical recovery.
3. The visual workflow's `widgets_values` for the bound ShowText node. The
   promoted text may be nested in one or more lists (for example
   `[["sfw-zimage-por-v3-03786"]]`); extraction walks nested lists in order
   before treating the snapshot as empty.
4. The API graph's `text_0` widget cache as a last-resort candidate.

The API graph remains authoritative for node classes, links, and execution
topology. Its cached `text_0` is not authoritative for dynamic prompt-library
text because it can predate the execution that produced the image. After
changing extraction precedence or nesting support, rebuild the materialized
index with `python -m comfy_gallery_core.cli rebuild-prompt-index` so existing
media rows reflect the corrected interpretation. The rebuild is idempotent and
does not rewrite embedded evidence.

## Registry record

Each entry stores:

- `source` and the zero-padded `index` from the Prompt ID;
- positive and optional negative prompt text;
- source metadata and origin (`xanta-utils` by default).

Character LoRA and ordinary LoRA lists are deliberately not part of a registry
entry. They remain media/workflow evidence and can vary between generations
that reuse the same prompt library item.

The implementation exposes authenticated list, lookup, create, update, and bulk
upsert/import API operations. It also exposes a source-only suggestion endpoint
for the Prompt Registry combobox; that endpoint never searches the large prompt
text column. Lookup returns every media whose trusted Prompt ID resolves to the
requested source/index, including IDs that have not been registered yet.
This makes stale or incomplete Xanta libraries discoverable without inventing a
prompt definition.

Trusted media Prompt IDs are materialized in `media_prompt_index`, keyed by the
media UUID and indexed by normalized source plus a canonical numeric index
string. This preserves numeric-equivalence lookup for padded IDs without
limiting valid 128-digit indexes to a database integer type. New workflow
extractions and verified display recovery update the row automatically. After
the migration is deployed, backfill existing media with:

```bash
uv run --package comfy-gallery-core python -m comfy_gallery_core.cli rebuild-prompt-index
```

Until every media row has been backfilled, lookup keeps the previous workflow
scan as a correctness-preserving fallback. Applying a new display profile also
rebuilds the index so profile-backed candidates do not become stale.

## Import contract

Use `POST /api/v1/prompt-registry/import` for bulk imports. The request body is a
JSON object with one `entries` array:

```json
{
  "entries": [
    {
      "source": "sfw-zimage-por-v3",
      "index": "03786",
      "prompt": "...",
      "negative_prompt": "...",
      "metadata": {
        "tags": ["portrait"]
      },
      "origin": "xanta-utils"
    }
  ]
}
```

The importer MUST follow these rules:

- `source` is required, trimmed, and limited to 256 characters. Matching is
  case-insensitive, while the first stored display spelling is preserved.
- `index` is required, digits only, and limited to 128 characters. Leading zeroes
  are significant for display and MUST be preserved.
- `prompt` and `negative_prompt` are plain text. Each is limited to 200,000
  characters; `negative_prompt` may be `null`.
- `metadata` is a JSON object and SHOULD contain source-specific provenance such as
  tags or the original filename. Character LoRA and ordinary LoRA lists MUST NOT be
  copied into the registry entry; they remain media/workflow evidence.
- `origin` identifies the producer, defaults to `xanta-utils`, and is limited to 64
  characters.
- A batch contains 1–2,000 entries and the received encoded request body is
  limited to 8 MB (oversized bodies return HTTP 413). The API writes a batch
  with one database upsert statement and one commit.
  After the bulk path is deployed, operators MAY use the full 2,000-entry limit;
  smaller batches remain appropriate when testing a new endpoint or network path.
- A batch MUST NOT contain duplicate `(source, index)` keys. Across requests the
  operation is an idempotent upsert keyed by normalized source plus index.

The response is returned only after the committed rows are read back from the
database, so `created_count`, `updated_count`, and `entries` describe persisted
records. A successful import is an HTTP 200 response. Validation errors are HTTP
422 and do not partially apply the request; an oversized encoded body is HTTP
413.

If a client receives a 5xx response, it SHOULD first query the registry by source
and compare the expected indexes before retrying. Retrying the same batch is safe
because the operation is an upsert; clients MUST NOT generate new indexes to work
around a failed response. Prompt Registry import is independent of node/model
registry synchronization and does not require a live ComfyUI connection.

For source selection, use `GET /api/v1/prompt-registry/sources?q=<prefix>&limit=24`.
It returns distinct display source labels and intentionally does not search prompt
text or calculate a full registry count.

## Read API extensions

All read endpoints require the existing authenticated session or Bearer API
token. A prompt is **materialized** when at least one linked media record is
favorited and not in Trash. Trash outranks Favorite, so a trashed favorite does
not materialize its prompt; media that is neither favorited nor trashed is
ordinary media and does not materialize either. `media_prompt_index` still
records generation history, and Trash never erases it.

```text
GET /api/v1/prompt-registry/random
  ?source=<optional-source>
  &materialization=any|materialized|unmaterialized

GET /api/v1/prompt-registry/stats
  ?source=<optional-source>

GET /api/v1/prompt-registry/neighbor
  ?source=<source>
  &index=<numeric-index>
  &direction=previous|next

GET /api/v1/prompt-registry/heatmap
  ?source=<optional-source>
  &include_not_faved=false
  &include_trash=false
  &limit=20000
  &offset=0
```

`random` combines `source` and `materialization` with AND semantics and returns
HTTP 404 with `PROMPT_REGISTRY_RANDOM_NOT_FOUND` when no entry matches. The
random response includes the stable `prompt_id` and the favorited, non-trashed
`media_count` for that entry.
`stats` reports registered, materialized, and unmaterialized entry counts using
the same favorite-based definition.
`neighbor` returns the nearest registered entry in numeric index order, skipping
gaps instead of requiring the caller to probe every integer.
`heatmap` returns compact contribution-matrix cells for every registered prompt.
Each cell includes the stable `prompt_id`, its source/index, and the number of
linked media in the requested scope. The default scope is favorites outside
Trash; `include_not_faved=true` adds ordinary media and `include_trash=true` adds
Trash. Results are ordered by source and numeric index, support an optional
source filter, and expose `total` and `max_media_count` so clients can build a
relative color scale without loading media records.

The frontend provides a Prompt Registry page under **System → Prompt Registry**.
Prompt IDs in Media Detail are links to that page, where the definition and all
matching media can be inspected. The lookup response marks each media record with
`is_trash` so the client can present Trash distinctly; Trash outranks Favorite in
that presentation as well.

## Adapter mapping example

The registry API intentionally accepts a neutral record shape so an adapter can
translate whichever file format a local Xanta Utils installation uses:

```json
{
  "source": "sfw-zimage-por-v3",
  "index": "03786",
  "prompt": "...",
  "negative_prompt": "...",
  "metadata": {}
}
```

No ComfyUI connection is required to browse or resolve existing registry data.
