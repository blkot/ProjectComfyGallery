# Display declarations and historical recovery

A **display field** describes how the owner wants one output presented in the web
Media Detail sidebar. The supported fields are base model, LoRA list, character
LoRA, positive prompt and prompt library ID. A prompt library ID is opaque text
and preserves leading zeros. It is neither a ComfyUI execution ID nor a global
foreign key into a library service. Character LoRA is an explicit role, not
something inferred from the first LoRA or its filename.

For each field independently, the Detail view prefers an explicit declaration
on the output PNG, then a verified historical value, then the existing workflow
interpretation where one exists. New fields with no value need no placeholder.
An explicit empty string or empty stack is distinct from an absent field.
Original workflow evidence remains inspectable. This display overlay does not
change the media UUID, embedded evidence, model usages, keyword index, blind
review or analytics.

## New images: declare values at the save boundary

[Patch for the Xanta saver](../../integrations/comfyui/xanta_save_display_fields/nodes.patch).
The standard hidden ComfyUI PROMPT input remains unchanged. The five new
optional sockets use the `cg_` prefix:

| Socket | Connect | Meaning |
| --- | --- | --- |
| cg_base_model | STRING | Human-facing base model name, not a MODEL object |
| cg_lora_list | STRING or LORA_STACK | Loader's formatted text or evaluated stack of name/model strength/CLIP strength triples |
| cg_character_lora | STRING | Character LoRA name declared for this output |
| cg_prompt | STRING | Final positive text being encoded |
| cg_prompt_id | STRING | Prompt Library's second output (output index 1) |

Only connected values are written. Each saver copies EXTRA_PNGINFO, reserves
`comfy_gallery_display_v1`, and declares values for its own output; it never
mutates the shared dictionary or forwards another saver's declaration. The
versioned envelope contains `version`, `save_node_id`, and `fields`. The
reader verifies the saver class and the corresponding socket's source link in
the embedded API graph before accepting a field. Validation failures drop only
the affected field when possible. Existing workflow and recorder metadata are
preserved. The current carrier is PNG.

## Historical files: define the meaning once, then prove the value per output

A recovery profile pins a reference media ID, the visual workflow UUID, a
structural signature, and a field-to-ShowText mapping. The signature includes
API node IDs and classes, source/destination wiring and output slots,
ShowText titles, prompt library identity and regex settings. Seeds, prompt
contents and cached display text can change without creating a new profile.
The profile fingerprint also includes the bindings themselves. A structural
revision requires review; identical node numbers are insufficient. Without
a workflow UUID, only the reference media itself is eligible. Even a matching
profile is never an instruction to change all matching media: each invocation
names one candidate and one execution explicitly.

A ShowText widget snapshot can predate the job. Recovery accepts only a single
actual text output from each bound ShowText node in a successful retained job.
The execution workflow must match the target. The Xanta saver must list the
output, and its bytes must match the Gallery original size and SHA-256.
No job, missing/ambiguous output, conflicting existing receipt, or scope
mismatch means no write. An archive stores the history, locator and verified
output so operator-controlled recovery also works after a ComfyUI restart.
Keep these archives private: they contain the original PNG and workflow text.

Run inside the updated Gallery backend environment after applying its normal
migration (0016). Commands preview unless `--apply` is present:

```sh
python -m comfy_gallery_core.cli recover-display \
  --reference-media REFERENCE_UUID --media MEDIA_UUID --job JOB_UUID \
  --bind prompt_id=827 --bind character_lora=835 \
  --archive-out /private/output-proof.zip --profile-out /private/workflow-profile.json

python -m comfy_gallery_core.cli recover-display \
  --profile /private/workflow-profile.json --media MEDIA_UUID --job JOB_UUID \
  --offline /private/output-proof.zip --apply
```

Reuse a saved profile for another explicitly selected media/job pair. Omit
`--job` to inspect the matching media's embedded widget text as unverified
candidates only; it cannot be applied as a recovered field. Omit
`--offline` to use the configured ComfyUI server while it retains the job.
There is no bulk mutation by node ID. Verified values live in
`workflow_display_recovery`, independently of extraction runs; an ordinary
**Reprocess** retains them but does not initiate historical recovery. Replaying
the same verified receipt is idempotent. The database backup and portable
workflow-evidence export include these records.

## Library-wide migration without ComfyUI

The normal migration reads Gallery's saved workflow snapshots. Preview and
install the operator-approved profile from the Gallery backend:

```sh
python -m comfy_gallery_core.cli migrate-display --profile /private/workflow-profile.json
python -m comfy_gallery_core.cli migrate-display --profile /private/workflow-profile.json --apply
```

The preview counts the workflow UUID population, exact graph matches and
available embedded widget strings for each field. Applying stores one mapping,
not a rewritten copy of each media record. The detail API projects matching
values from each snapshot, including subsequent imports, in a separate
**Embedded workflow text** section. It never treats those strings as executed
values, changes a model index, or consults ComfyUI. Explicit per-output or
independently verified fields take precedence. Profiles without a workflow UUID
apply only to their reference media. Installing a conflicting mapping for the
same scope and graph is rejected.
