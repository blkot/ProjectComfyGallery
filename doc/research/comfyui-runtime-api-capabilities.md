# ComfyGallery integration with a running ComfyUI instance

**Status:** Research complete; design input, not yet implemented

**Date:** 2026-08-27

**Source snapshots:** ComfyUI
[`d8e7bbc`](https://github.com/Comfy-Org/ComfyUI/tree/d8e7bbc9d586d95f758d6b0ed23d519088be578a),
ComfyUI Frontend
[`064bf09`](https://github.com/Comfy-Org/ComfyUI_frontend/tree/064bf09bbd4a6b5026211e0f3a2d2753cbe838ac),
and ComfyUI-Manager
[`f39cbd5`](https://github.com/Comfy-Org/ComfyUI-Manager/tree/f39cbd56fecae0b27a446c0cd450cd591f3a8bea).
Links to source below are pinned to those revisions.

## Conclusion

A running ComfyUI instance is useful to ComfyGallery in four ways:

1. **Live definition registry:** `/object_info` describes every currently loaded
   core and custom node, while `/models`, `/embeddings`, and optional Manager
   endpoints expose useful inventory. ComfyGallery can turn each successful
   connection into an immutable node-definition snapshot and use it to improve
   first-run semantic mapping.
2. **Same-process execution catch-up:** `/history`, `/queue`, and the newer
   `/api/jobs` projection expose prompts and output references for executions
   still retained by the current ComfyUI process. ComfyGallery can reconcile
   these records idempotently by `prompt_id` and content SHA-256.
3. **Byte transfer:** `/view` can retrieve a known input, output, or temporary
   file without changing its bytes; `/upload/image` can place an image into a
   ComfyUI input directory. This supports capture of workflow inputs and a
   future round trip from Gallery back to ComfyUI.
4. **Saved-workflow discovery:** `/v2/userdata` and `/userdata/{file}` can list
   and read server-stored workflow JSON. These are reusable definitions, not
   generation history.

The important negative finding is that **ComfyUI cannot reconstruct generation
history for old output files after a normal restart**. `PromptQueue` creates
empty in-memory `queue`, `currently_running`, and `history` containers on server
construction; completed records are added only by `task_done()`, and the
history is finite and can be cleared or deleted
([PromptQueue source](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/execution.py#L1249-L1398)).
The `/history` and current `/api/jobs` routes read that same `PromptQueue`
object; neither scans the output directory
([history/jobs routes](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L821-L1063)).

Therefore ComfyUI should be treated as a **live enrichment source**, while
ComfyGallery remains the durable ledger. Existing files and their embedded
workflow metadata remain the recovery path after a restart.

## Capability and durability matrix

| Surface | Useful data or action | Lifetime | Recommended use |
| --- | --- | --- | --- |
| `GET /system_stats` | ComfyUI version, package versions, Python, launch arguments, devices | Current process/configuration | Connection health and compatibility diagnostics only |
| `GET /features` | Server capability flags, including upload limit and whether experimental assets are enabled | Current process/configuration | Feature detection; never infer support only from a version string |
| `GET /object_info` and `/object_info/{class}` | Loaded node classes, required/optional/hidden inputs, input order, outputs, display name, module, category, flags | Current loaded packages | Snapshot and fingerprint node definitions; suggest semantic mappings |
| `GET /models`, `/models/{folder}`, `/embeddings` | Registered model categories and filenames | Current filesystem/configuration | Reconcile names seen in embedded workflows; not a content identity |
| `GET /view_metadata/{folder}?filename=...` | `__metadata__` from a `.safetensors` header | Durable model-file data | Optional model enrichment; no GGUF or sidecar JSON support |
| `GET /queue`, `GET /prompt` | Running/pending prompts and queue count | Volatile | Operational status and immediate catch-up |
| `GET /history`, `/history/{prompt_id}` | Completed prompt tuple, API prompt, extra data, status messages, node output references | Volatile, bounded, manually clearable | Same-process catch-up and correlation |
| `GET /api/jobs`, `/api/jobs/{id}` | New normalized queue/history projection with status, workflow ID, outputs and errors | Volatile; same backing store as history | Prefer when detected, fall back to `/history` |
| `WS /ws?clientId=...` | Queue status and execution messages | Connection/process lifetime | Wake reconciliation promptly; not a durable event log |
| `GET /view` | Original bytes for a known `filename`/`subfolder`/`type` or asset hash | As long as the referenced file exists | Stream into Gallery with limits, then hash and store |
| `POST /upload/image` | Add image bytes to input/output/temp with duplicate-name handling | Filesystem | Future Gallery-to-ComfyUI input handoff |
| `GET /v2/userdata`, `GET /userdata/{file}` | Server-saved workflows, settings-adjacent files, templates | Filesystem | Optional read-only workflow library import |
| `GET /settings`, `/users` | Frontend preferences and user profile selection | Filesystem | Connection diagnostics only; not provenance |
| Experimental `/api/assets` | Indexed files, BLAKE3 when enriched, tags, loader path, and sometimes `job_id` | Database/filesystem | Optional output discovery and correlation, behind capability flag |
| ComfyUI-Manager read APIs | Installed packages, node-to-package mappings, Manager version | Manager installation/configuration | Optional node package/version enrichment only |

The stable route list and intended purposes are documented in the official
[ComfyUI server routes reference](https://docs.comfy.org/development/comfyui-server/comms_routes).
`/system_stats`, `/features`, model listing, safetensors metadata, and the
complete node schema are implemented together in the current
[server routes](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L337-L819).

## What can and cannot be recovered after restart

### What is lost

- The pending queue, running set, completed history, status-message timeline,
  and the association from a completed prompt to all of its output nodes are
  process memory.
- A new process cannot answer `/history/{old_prompt_id}` unless another
  extension has independently persisted and restored it. Core ComfyUI does not
  do that.
- Core history also has `MAXIMUM_HISTORY_SIZE = 10000` and supports explicit
  clear/delete operations, so it is not durable even without a restart
  ([history storage](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/execution.py#L1249-L1398),
  [history mutation route](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L1203-L1217)).

### What survives

- The output file itself and whatever its save node embedded.
- A built-in `SaveImage` PNG contains an API-format `prompt` and values from
  `extra_pnginfo` unless ComfyUI was launched with metadata disabled. The
  normal frontend submits the visual workflow as
  `extra_data.extra_pnginfo.workflow`
  ([SaveImage implementation](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/nodes.py#L1659-L1721),
  [frontend queue request](https://github.com/Comfy-Org/ComfyUI_frontend/blob/064bf09bbd4a6b5026211e0f3a2d2753cbe838ac/src/scripts/api.ts#L1049-L1084)).
- Built-in video saving also writes the prompt and extra metadata to the
  container when metadata is enabled
  ([video save implementation](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/comfy_extras/nodes_video.py#L1-L58)).
  Custom video/save nodes remain node-specific, so Gallery's embedded-metadata
  parser is still required.
- Server-saved workflow JSON under the user directory survives, but it is a
  mutable reusable workflow, not proof of which graph or values produced a
  particular file. The userdata routes merely expose those files
  ([user-data routes](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/app/user_manager.py#L126-L464)).

### Experimental assets do not restore history

Current ComfyUI has an opt-in assets database behind `--enable-assets`. It can
scan `models`, `input`, and `output`, list assets, serve content, and record a
`job_id` on an output that was registered at the end of a live execution
([asset routes](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/app/assets/api/routes.py#L295-L402),
[live output registration](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/main.py#L318-L421)).
That association can survive a ComfyUI restart if assets were enabled when the
file was produced.

It still is not a replacement for Gallery history:

- A later seed of already-existing output files has no historical prompt/job
  ID to recover.
- The current scanner extracts filesystem metadata and selected safetensors
  metadata; it does not parse image/video workflow metadata
  ([metadata extractor](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/app/assets/services/metadata_extract.py#L1-L281)).
- The source explicitly warns that the asset system is not fully implemented
  and its API must not yet be treated as stable
  ([asset API warning](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/app/assets/api/routes.py#L91-L107)).

Use it as a feature-detected accelerator, never as the only discovery or
provenance mechanism.

## Identifiers and correlation quality

| Identifier | Where it appears | Reliability |
| --- | --- | --- |
| Gallery media UUID | Gallery database and API | Durable Gallery identity; authoritative |
| Gallery SHA-256 | Bytes imported into Gallery | Durable content identity and duplicate key |
| ComfyUI `prompt_id` | Queue/history, WebSocket messages, current job API; optional asset `job_id` | Excellent execution-occurrence key while captured, but not generally embedded in saved media |
| Output reference | `filename`, `subfolder`, `type` in node UI outputs/history | Exact lookup key for `/view` at that moment; filenames can later be renamed or overwritten |
| Visual workflow `id` | Normal frontend's `extra_pnginfo.workflow.id`; current jobs API projects it | Useful grouping hint, but a workflow is mutable and the field may be absent |
| Embedded API prompt/workflow | Saved media metadata | Best surviving generation evidence; format and completeness depend on save node/settings |
| ComfyUI asset reference/BLAKE3 | Experimental asset API | Useful local lookup/dedup hint; feature-gated and not Gallery's identity |
| Model filename | Node input and `/models/{folder}` | Name resolution only; not unique content identity |

The current `/api/jobs/{id}` implementation returns the API prompt, extra data,
normalized outputs, and status details for a retained job. It extracts
`workflow_id` from `extra_pnginfo.workflow.id`
([job normalization](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/comfy_execution/jobs.py#L105-L223)).
Current `POST /prompt` also accepts an optional caller-provided canonical UUID
as `prompt_id`, which would give Gallery a deterministic correlation key if
Gallery later submits executions itself
([prompt submission](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L1072-L1144)).
Older versions should be assumed to mint the ID and return it.

## WebSocket limitation for passive observation

The official message set includes `execution_start`, `execution_cached`,
`executing`, `progress`, `executed`, terminal success/error/interruption, and
queue `status`
([message reference](https://docs.comfy.org/development/comfyui-server/comms_messages)).
It looks like a global event stream, but it is not one for ordinary frontend
executions:

1. The frontend sends its own WebSocket `client_id` in `POST /prompt`.
2. During execution, ComfyUI assigns that value as the active client and sends
   most detailed events to that socket ID.
3. Queue `status` updates are sent without a socket ID and therefore broadcast.

This follows from the current
[WebSocket/session handler](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L269-L328),
[execution message dispatch](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/execution.py#L672-L836),
and [broadcast implementation](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L1380-L1400).
Therefore a separate Gallery socket should use broadcast `status` as a
**wake-up hint**, then query `/history` or `/api/jobs`. It must not assume it
will receive another browser tab's `executed` or terminal event.

There is also a completion race: `execution_success` is emitted inside the
executor, while `PromptQueue.task_done()` records history only after execution
returns to the worker
([worker ordering](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/main.py#L367-L421)).
Any event-driven client must retry a missing history item briefly rather than
treating the first `404`/empty result as permanent.

## Recommended integration cycle

### 1. Pair a connection, not an instance identity

Store an operational connection profile with:

- configured base URL;
- optional fixed request headers, including `comfy-user` for multi-user mode;
- last successful feature/version probe;
- connection health and last sync timestamps.

Do not use this record as generation provenance. The same ComfyUI files can be
served by different installs, versions, or machines, and the product has already
decided not to manage ComfyUI instances as domain entities.

The Gallery backend—not a browser—should make these calls. Allow only an
administrator-configured origin, cap response bytes and time, reject redirects
to another origin, and never accept an arbitrary fetch URL from a media field.
Core `comfy-user` selection chooses a data directory; it is not authentication
([user selection](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/app/user_manager.py#L36-L70)).
Use network isolation or a reverse proxy if the ComfyUI API needs access
control.

### 2. Capability handshake on connect and reconnect

Read, with bounded timeouts:

1. `/system_stats`
2. `/features`
3. `/object_info`
4. `/models`, then configured interesting folders such as `checkpoints`,
   `diffusion_models`, `unet`, and `loras`
5. `/embeddings`
6. optional `/manager/version` and `/customnode/getmappings`

Hash a canonical form of every node definition and store an immutable snapshot
when it changes. A definition includes class name, `python_module`, display
name, category, input schema/options, output schema, and flags. `/object_info`
calls the live `INPUT_TYPES()` implementation for every loaded node, so it is a
strong source for candidate value locators, but class/input names still do not
prove that a value semantically means checkpoint, LoRA, or positive prompt.
Gallery's semantic registry and manual correction remain authoritative
([node-info builder](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L751-L819)).

Manager is now under the Comfy organization and documents read endpoints for
installed packages and node-to-package mappings
([Manager OpenAPI](https://github.com/Comfy-Org/ComfyUI-Manager/blob/f39cbd56fecae0b27a446c0cd450cd591f3a8bea/openapi.yaml#L174-L263)).
Use those only when present. They do not replace the user's separate LoRA
Manager adapter and should not grant Gallery access to Manager's install,
update, reboot, or other mutation endpoints.

### 3. Reconcile retained executions immediately

On initial connection and after every reconnect:

1. Query `/queue`.
2. Prefer `/api/jobs` when detected; otherwise query
   `/history?max_items=<bounded window>`.
3. For each unseen `prompt_id`, persist an execution occurrence containing the
   raw prompt/history projection and every output reference.
4. For each media output, request original bytes through `/view` using the
   returned `filename`, `subfolder`, and `type`.
5. Compute Gallery SHA-256 while streaming. Import new bytes; if the content is
   already managed, attach only the new execution/source occurrence.
6. Parse the managed file's embedded metadata independently and preserve it as
   ground truth.

`/view` returns the original file when neither preview nor channel transforms
are requested. It accepts a known input/output/temp reference and, in newer
asset-enabled builds, an asset hash
([view implementation](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L516-L659)).
Do not request `preview` or `channel`; those transform image bytes.

History has no stable cursor. Keep an idempotent set/table keyed by
`connection + prompt_id`, fetch a bounded recent window, and tolerate repeated
records. Content SHA-256 handles renamed paths and duplicate outputs; it must
not collapse two execution occurrences into one occurrence.

### 4. Stay near-real-time without trusting the socket as a log

- Keep a separate `/ws?clientId=<gallery-observer-id>` connection.
- Debounce each broadcast `status` update into a history/jobs reconciliation.
- Add a slow periodic reconciliation while connected in case a socket message
  is missed.
- On disconnect, mark the connection unavailable but do not fail already
  imported media.
- On reconnect, repeat the bounded history catch-up before live watching.

This is deliberately pull-based for executions created by the normal ComfyUI
frontend. It is low-frequency on a local network and avoids unsupported
monkey-patching of the executor.

### 5. Keep direct Gallery upload as the durable fast path

The ComfyGallery output custom node remains the most reliable path for new
generations because it runs in the workflow, can receive the hidden API prompt
and extra workflow metadata, and can publish the final bytes directly. The
history reconciler is a safety net for ordinary save nodes and sessions in
which the Gallery node was absent or failed.

Both paths must converge on the same import service and SHA-256 idempotency
rules. A direct upload followed by history reconciliation should add missing
execution/source context, not create a second media record.

### 6. Recover after a ComfyUI restart from files, not history

After restart:

1. Re-run the capability and node/model snapshot sync.
2. Reconcile whatever new in-memory history exists.
3. Rescan Gallery's configured import roots for new files.
4. If Gallery cannot see the remote output directory and the experimental
   assets API is enabled, optionally trigger/read an output asset seed and
   import newly listed output assets.
5. Parse embedded metadata from each imported file; do not wait for an old
   ComfyUI history entry that cannot return.

There is no stable core endpoint that enumerates the legacy output directory.
Without the experimental assets API, Gallery needs either filesystem access,
known `/view` references captured before restart, or an explicit custom
ComfyUI endpoint/node.

### 7. Add a controlled Gallery-to-ComfyUI round trip later

For a Gallery workflow reopened in ComfyUI:

1. Resolve each captured input media record in Gallery.
2. Upload missing images through `/upload/image` and record the returned
   `name`, `subfolder`, and `type`.
3. Rewrite only the mapped loader values in a copy of the preserved workflow.
4. Hand the workflow to the existing ComfyUI browser bridge.

The official upload route handles filename conflicts and returns the final
reference
([upload implementation](https://github.com/Comfy-Org/ComfyUI/blob/d8e7bbc9d586d95f758d6b0ed23d519088be578a/server.py#L389-L469)).
Video upload is not provided by the legacy core upload route, so captured video
inputs need the experimental asset upload, a purpose-built custom endpoint, or
shared filesystem access.

## Proposed implementation boundaries

Keep the connector modular so ComfyUI changes do not leak into ingestion:

```text
ComfyUIConnectionClient
  probe_capabilities()
  fetch_node_definitions()
  fetch_model_inventory()
  fetch_retained_executions()
  fetch_media(reference)
  watch_status_wakeups()

ComfyUIReconciler
  snapshots definitions/inventory
  records prompt/output occurrences
  calls the existing media import service
  owns retries, windows, and cursors

Existing Gallery ingestion
  streams bytes
  computes SHA-256
  deduplicates content
  preserves embedded metadata
  queues workflow parsing
```

Optional adapters should sit beside the core connector:

- `ComfyUIManagerInventoryAdapter`
- the existing LoRA Manager registry adapter
- `ComfyUIExperimentalAssetsAdapter`

The core connector must remain useful when all three are absent.

## Failure and drift rules

- Treat endpoint `404`, `405`, and asset `503 SERVICE_DISABLED` as unsupported
  capability, not a broken Gallery deployment.
- Store raw successful responses before normalizing them so schema drift can be
  diagnosed.
- Never overwrite an old node-definition snapshot; custom nodes can reuse the
  same class name after an upgrade with a different schema.
- An output reference that now returns different bytes is a new content import,
  not an update to an older Gallery media record.
- A history item can exist before every post-execution enrichment step is
  visible. Retry missing `/view` or asset data with a short bounded backoff.
- A missing model filename in the current instance must not invalidate an old
  media workflow. Preserve it as unresolved historical evidence.
- Do not make workflow parsing depend on ComfyUI being online. Live definitions
  improve suggestions; Gallery's stored semantic mappings and raw embedded
  workflow remain sufficient offline.

## Recommended MVP slice

The smallest high-value implementation is:

1. read-only connection configuration and health probe;
2. node-definition snapshot sync from `/object_info`;
3. model filename sync from `/models/{folder}`;
4. manual **Sync retained ComfyUI history** action using `/history` and `/view`;
5. SHA-256-idempotent import through the existing pipeline;
6. stored `prompt_id`, raw history evidence, node output ID, and source file
   reference on the import occurrence;
7. clear UI disclosure that the sync window resets when ComfyUI restarts.

After this proves reliable, add WebSocket status wake-ups and periodic
reconciliation. Experimental assets and Manager enrichment should be later,
feature-detected additions rather than MVP dependencies.
