# Record Execution for Gallery (ComfyUI)

For PNGs produced with dynamic prompt libraries, wildcards or LoRA Manager cyclers.
The node passes the image through unchanged and records the **evaluated** strings
and/or LoRA stack in that execution's PNG metadata. No Gallery token or network
request is needed. The existing save/upload node still controls where the file goes.

1. Copy this whole directory into ComfyUI's `custom_nodes/` and restart ComfyUI.
2. Put **Record Execution for Gallery** between the final IMAGE and the existing
   PNG save/upload node. Its output is the same IMAGE.
3. Branch the **exact same STRING output** that feeds the CLIP text encoder into
   the recorder's positive or negative input. For a LoRA Manager Prompt encoder,
   branch its final PROMPT output instead. Gallery follows node IDs and output
   slots; the labels on the recorder are wiring hints.
4. Branch the **same LORA_STACK output** that feeds the LoRA Manager Loader into
   the recorder's stack input. An empty recorded stack means no selected LoRAs.
5. Save/upload the resulting PNG with metadata enabled. The saver must serialize
   *all* entries in ComfyUI's `EXTRA_PNGINFO`, including
   `comfy_gallery_execution_v1`, alongside the normal prompt and workflow.
   Verify the extra key on one newly imported PNG before queuing a batch.

For the library → text merge → CLIP and cycler + stacker → combiner → loader
workflow, connect the text **merge output** and the **combiner output**. Do not
connect a library label, template, prior UI result or candidate pool.

This version supports the PNG text-chunk carrier; video containers or savers that
discard extra metadata do not gain execution records. Put the recorder on the
save branch only, downstream of expensive generation. If list-mapped calls
record differing values for the same wire, the value is left unresolved. The
gallery can record workflow-level evidence from multiple branches; membership
in an embedded graph alone does not prove every branch contributed to an image.
