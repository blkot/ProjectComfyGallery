# Workflow Intelligence and Offline Node Registry

**Status:** Accepted

**Implementation:** Layers 1–2 and conservative named-input observations were
implemented in Phase 2. Phase 3 implements the offline node-definition registry,
automatic/manual mappings, historical compatibility matching, model resolution, and
pipeline-role classification. See
[Phase 3 verification](../development/phase-3-node-model-registries.md).

## Purpose

Workflow intelligence converts heterogeneous embedded ComfyUI metadata into useful, versioned facts without assuming that every custom node or historical workflow is known.

The design prioritizes:

- Complete preservation.
- Structural parsing before semantic interpretation.
- Automatic first-pass classification.
- Offline operation.
- Correctable and explainable inference.

## Input representations

ComfyUI media may contain:

- An API-format prompt graph with node IDs, `class_type`, and named `inputs`.
- A visual workflow graph with nodes, links, properties, modes, and `widgets_values`.
- Extra PNG information or custom output-node metadata.
- One representation without the other.
- Malformed, truncated, disabled, or absent metadata.

The API prompt and visual workflow are related but not interchangeable. Both are retained and parsed independently.

## Four-layer model

### Layer 1: embedded ground truth

Store exact decoded payloads and, where practical, raw payload bytes. No normalization or registry correction rewrites this layer.

### Layer 2: generic graph

Represent:

- Every node and original ID.
- Class/type, title, properties, mode, and raw widgets.
- Named API inputs.
- Every link and declared type.
- Constant values versus node references.

The generic graph must be useful even when no semantic extractor understands a node.

### Layer 3: semantic observations

Extract:

- Prompt fields and possible roles.
- Checkpoint and LoRA references.
- Model pipeline patterns and usage slots.
- Sampler/settings metadata retained for filtering.
- Dimensions, seeds, and other supported configuration facts.

Every observation carries evidence, confidence, extractor version, and correction precedence.

### Layer 4: evaluation and analysis

Evaluation never reads arbitrary widget positions directly. It consumes current semantic observations or raw prompt fields explicitly selected by the node registry.

## Parsing precedence

1. Use named API-prompt inputs when available.
2. Correlate API and visual nodes by original node ID.
3. Use the visual graph for links, titles, modes, and widgets absent from the prompt.
4. Use a compatible cached node definition to map widget positions when named input data is unavailable.
5. Use inference/manual mapping only when structural evidence is insufficient.

No lower-confidence interpretation removes higher-fidelity raw values.

## ComfyUI API assistance

On demand, the application may read:

- `GET /object_info`
- `GET /object_info/{node_class}`
- `GET /system_stats`
- `GET /features`
- `GET /models`
- `GET /models/{folder}`

The object-info schema can provide current:

- Required, optional, and hidden inputs.
- Input ordering and widget configuration.
- Output types and names.
- Node module/package, category, description, and search aliases.

Official references:

- <https://docs.comfy.org/development/comfyui-server/comms_routes>
- <https://docs.comfy.org/custom-nodes/backend/server_overview>
- <https://docs.comfy.org/custom-nodes/backend/datatypes>
- <https://docs.comfy.org/custom-nodes/backend/more_on_inputs>

### API limitations

The API does not standardize high-level meanings such as “second-pass checkpoint” or “LoRA application.” Custom nodes can use:

- Arbitrary custom datatypes.
- Wildcard inputs.
- Dynamically created inputs.
- Frontend-only widgets.
- Changed schemas across versions.

Deleted/uninstalled node definitions cannot be recovered from a current API. Therefore, live ComfyUI is enrichment only.

## Anonymous schema snapshots

The application does not model ComfyUI instances.

Each sync stores:

- Capture time.
- Reported ComfyUI version and package versions when returned.
- Raw object-info payload.
- Per-node normalized definition.
- Schema fingerprint.

When a historical workflow uses a class with multiple definition variants, structural compatibility determines the best candidate:

- Named input overlap.
- Widget count/order compatibility.
- Input/output type compatibility.
- Module hint compatibility.
- Graph-link fit.

If no safe fit exists, the node remains unresolved rather than being forced into the newest schema.

## Node-definition registry

Each definition variant records:

- Class/type and display name.
- Module/package.
- Input groups, names, types, options, and order.
- Output types and names.
- Category, description, aliases.
- Source and capture provenance.
- Schema fingerprint.
- First/last observation.

Built-in known definitions may ship with the application, but runtime snapshots remain versioned rather than overwriting them.

## Semantic mapping registry

A semantic mapping relates a node input or widget locator to a supported meaning:

- Checkpoint.
- LoRA.
- Prompt.
- Sampler/configuration.
- Other future typed semantics.

Mappings may be:

- Built-in confirmed.
- Manually confirmed.
- High-confidence inferred and active.
- Suggested/needs review.
- Unknown.

### Precedence

1. Manual correction.
2. Confirmed built-in mapping compatible with schema.
3. High-confidence active inference.
4. Suggested inference.
5. Unknown.

Manual overrides never modify the raw workflow or delete earlier extractor runs.

### Structured multi-LoRA values

Some LoRA loaders expose one mapped input as a structured collection rather than one
filename. For a mapping tagged as `lora_reference`, semantic extraction supports both
of these shapes:

```json
{"**value**": [{"name": "adapter_a", "active": true, "strength": "1.00"}]}
```

```json
[{"name": "adapter_a", "active": true, "strength": 1}]
```

Each object with a non-empty `name` and the explicit boolean `active: true` becomes a
separate LoRA semantic observation and subsequent model usage. Entries with
`active: false`, a missing/invalid `active` flag, or no name are not current usages.
Their values still remain in the generic workflow value and immutable embedded ground
truth.

Observation evidence records the collection container/index plus `strength` and
`clipStrength` when present. Strength is evidence/filtering metadata, not a dominant
MVP analysis factor. This rule is based on the semantic mapping and value shape, not a
hardcoded node title or one schema fingerprint, so a manual mapping can remain useful
across compatible loader variants.

## Automatic first-run classification

The application, not the user, performs the first pass.

Evidence may include:

- Known node class and package mappings.
- Exact input name patterns.
- Node descriptions/categories/search aliases.
- Input/output graph datatypes such as `MODEL`, `CLIP`, `CONDITIONING`, `LATENT`, and `SIGMAS`.
- File extension and path-like structure.
- Exact matches against LoRA Manager/model-registry values.
- COMBO option overlap with ComfyUI model-folder lists.
- Repeated value behavior across imported workflows.
- Graph position relative to known loaders/samplers/output nodes.

### Confidence states

- **Confirmed:** built-in compatible rule or manual correction; active.
- **High confidence:** inferred, active, visibly labeled.
- **Needs review:** plausible but excluded from analytical semantics.
- **Unknown:** structurally preserved with no semantic meaning assigned.

Evidence and confidence calculations are stored so the user can understand why a tag exists.

## Unknown-node inbox

The MVP inbox shows:

- Node class/module/schema variant.
- Number of affected media/workflows.
- Example raw nodes and values.
- Graph neighborhood.
- Candidate semantic tags and evidence.
- Current confidence/state.

The user can:

- Confirm a suggestion.
- Tag an input manually.
- Correct an active inference.
- Leave it unknown.
- Preview affected workflows before activation.

A saved mapping enqueues versioned reprocessing of affected snapshots.

The full arbitrary visual rule editor is deferred.

## Prompt handling

Prompt text is:

- Preserved exactly.
- Rendered as plain text.
- Never redacted or rewritten by the application.
- Separated into fields when semantic roles such as positive/negative are known.
- Labeled by node title/ID when the role is unknown.

Prompt classification may use graph connections into positive/negative conditioning, but uncertain role labels remain explicit. Prompt content is visible during evaluation; model and workflow configuration are not.

## Pipeline pattern and usage-slot inference

Pipeline patterns describe graph structure, not canonical model identity.

Initial supported patterns:

- Single-model.
- Dual-noise.
- Single-pass.
- Dual-pass.
- Unclassified.

Initial usage slots:

- Single.
- High-noise.
- Low-noise.
- First-pass.
- Second-pass.
- Unclassified.

Examples:

- Wan 2.1: one single-model slot.
- Wan 2.2: ordered high-noise and low-noise artifacts.
- Krea 2 single-pass: one Turbo-lineage artifact in the single slot.
- Krea 2 dual-pass: Raw first-pass plus a more result-dominant second-pass artifact.

Importance is not permanently assigned to the checkpoint artifact. Analysis chooses a focus slot within a pipeline-pattern cohort.

## Reprocessing

Triggers include:

- Parser/extractor version upgrade.
- New node definition.
- Mapping confirmation or correction.
- Model-registry link correction.
- Pipeline-pattern correction.
- Structured semantic-extractor upgrades.

Reprocessing:

1. Creates a new extraction run.
2. Reads immutable workflow evidence.
3. Records the node-registry/model-registry versions used.
4. Writes new observations.
5. Recomputes current semantic views by precedence.
6. Marks affected live analysis previews stale.
7. Never changes a saved analysis run.

Extractor `2.1.0` introduces active-only structured multi-LoRA expansion. After
upgrading from an earlier extractor, an operator runs the existing bulk “reprocess
all” action once. Reprocessing reads the preserved ground truth, replaces the current
derived model usages, and leaves prior extraction runs available for provenance.

## Failure behavior

- Missing metadata: media remains usable with `workflow_status = absent`.
- Malformed JSON: preserve payload and structured parse error.
- Unknown node: preserve graph and queue for review.
- ComfyUI offline: use cached definitions.
- Schema ambiguity: keep candidate list and no forced semantic tag.
- Extractor crash: retain prior successful observations and expose failed run.

## Golden-corpus dependency

Before parser behavior is considered stable, it must be tested against representative image and video media supplied by the user. The corpus is required to validate real metadata placement, custom nodes, multiple pipeline patterns, and VHS/video container behavior.

Phase 2 satisfied this dependency with 6 PNG images and 8 MP4 videos. Thirteen carry
both representations and one is API-prompt-only. The private regression asserts raw
evidence integrity, structural graph coverage, unknown-node survival, and initial
checkpoint/LoRA observations without committing private prompt or model content.
