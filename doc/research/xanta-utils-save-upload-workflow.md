# Xanta Utils Save & Upload workflow preservation

**Checked:** 2026-11-02

## Conclusion

The Gallery-side integration is designed to preserve embedded workflow metadata,
but this repository does not vendor the installed `ComfyUI-Xanta-Utils` source,
so the exact behavior of a particular local Xanta Utils checkout cannot be
verified here. The compatibility patch targets an external
`ComfyUI-Xanta-Utils/nodes.py` and assumes that its `XantaSaveAndUpload` node
already follows ComfyUI's PNG save path.

For a compatible node with metadata enabled, the answer is **yes**: it should
preserve the normal ComfyUI `prompt` and `EXTRA_PNGINFO` entries, including the
embedded visual workflow. The Gallery only receives the final bytes; it does not
reconstruct a workflow after upload.

For an unpatched or incompatible checkout, the answer is **not guaranteed**.
If the node drops `EXTRA_PNGINFO`, re-encodes the image without PNG metadata, or
ComfyUI runs with metadata disabled, the uploaded image will not contain the
embedded workflow and Gallery cannot recover it from the upload request.

## Evidence

1. The integration guide explicitly assigns metadata preservation to the
   ComfyUI node and exact-byte storage to Gallery
   ([`doc/interfaces/comfyui-custom-node-upload.md:15-25`](../interfaces/comfyui-custom-node-upload.md)).
2. The guide requires a V1 image saver to accept hidden `PROMPT` and
   `EXTRA_PNGINFO` inputs, then follow ComfyUI's `SaveImage` behavior
   ([`doc/interfaces/comfyui-custom-node-upload.md:234-270`](../interfaces/comfyui-custom-node-upload.md)).
   It also states that metadata-disabled ComfyUI launches cannot be repaired by
   the uploader.
3. The Xanta patch is explicitly an external patch, not the node implementation
   shipped in this repository
   ([`integrations/comfyui/xanta_save_display_fields/README.md:1-7`](../../integrations/comfyui/xanta_save_display_fields/README.md)).
4. The patch adds hidden `prompt`, `extra_pnginfo`, and `unique_id` inputs and
   writes `comfy_gallery_display_v1` into the same `extra_pnginfo` dictionary
   before the original save path runs
   ([`integrations/comfyui/xanta_save_display_fields/nodes.patch:7-17`](../../integrations/comfyui/xanta_save_display_fields/nodes.patch),
   [`integrations/comfyui/xanta_save_display_fields/nodes.patch:23-54`](../../integrations/comfyui/xanta_save_display_fields/nodes.patch)).
   This proves how the Gallery display-field extension expects the saver to carry
   extra metadata; it is not proof that every Xanta Utils version does so.
5. The execution-capture companion node mutates `EXTRA_PNGINFO` and instructs the
   downstream saver to serialize all entries alongside the normal prompt and
   workflow
   ([`integrations/comfyui/comfy_gallery_execution_capture/README.md:3-20`](../../integrations/comfyui/comfy_gallery_execution_capture/README.md)).

## Recommended local verification

Inspect the installed Xanta Utils `nodes.py` and confirm all of the following:

- `XantaSaveAndUpload.INPUT_TYPES()` declares hidden `prompt: PROMPT` and
  `extra_pnginfo: EXTRA_PNGINFO` inputs.
- The save method passes the received prompt and extra PNG info to the PNG
  metadata writer instead of creating a new pixel-only image.
- The node uploads the exact path it just saved, not a preview or re-encoded
  derivative.
- ComfyUI is not started with metadata disabled.

Then generate one PNG, import it, and inspect the original bytes/metadata before
batch generation. Gallery's acceptance target is that the imported PNG exposes
the same raw prompt/workflow evidence as the local saved PNG
([`doc/interfaces/comfyui-custom-node-upload.md:333-345`](../interfaces/comfyui-custom-node-upload.md)).

If any check fails, apply the repository patch or update the Xanta node so its
save path preserves `PROMPT` and `EXTRA_PNGINFO` before uploading. No Gallery API
change is needed for that fix; the missing capability is at the ComfyUI saver
boundary.
