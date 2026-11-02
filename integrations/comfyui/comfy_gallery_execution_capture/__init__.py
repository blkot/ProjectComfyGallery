"""Record evaluated values on the image-saving branch, without changing the image."""

from __future__ import annotations

import math

CAPTURE_KEY = "comfy_gallery_execution_v1"


class RecordExecution:
    CATEGORY = "ComfyGallery"
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "record"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"image": ("IMAGE",)},
            "optional": {
                "positive": ("STRING", {"forceInput": True}),
                "negative": ("STRING", {"forceInput": True}),
                "stack": ("LORA_STACK",),
            },
            "hidden": {"extra_pnginfo": "EXTRA_PNGINFO", "unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # EXTRA_PNGINFO belongs to this execution. Only this tap and its downstream
        # saver need to run on a cache hit; leave the sampler upstream of the tap.
        return float("nan")

    def record(
        self, image, positive=None, negative=None, stack=None, extra_pnginfo=None, unique_id=None
    ):
        if isinstance(extra_pnginfo, dict) and unique_id is not None:
            records = extra_pnginfo.setdefault(CAPTURE_KEY, {})
            if isinstance(records, dict):
                record = records.setdefault(str(unique_id), {})
                if isinstance(record, dict):
                    for key, value in (
                        ("positive", positive),
                        ("negative", negative),
                        ("stack", stack),
                    ):
                        if value is None:
                            continue
                        if key == "stack":
                            # Accept the LoRA Manager triple format only. Unknown custom
                            # objects must never make the downstream PNG writer fail.
                            if not isinstance(value, (list, tuple)) or not all(
                                isinstance(entry, (list, tuple))
                                and len(entry) == 3
                                and isinstance(entry[0], str)
                                and all(
                                    type(x) is int or (type(x) is float and math.isfinite(x))
                                    for x in entry[1:]
                                )
                                for entry in value
                            ):
                                value = None
                            else:
                                value = [list(entry) for entry in value]
                        elif not isinstance(value, str):
                            value = None
                        # Several list-mapped calls can share the same node ID. Do not
                        # attribute any one of their differing values to every image.
                        if key in record and record[key] != value:
                            value = None
                        record[key] = value
        return (image,)


NODE_CLASS_MAPPINGS = {"ComfyGalleryRecordExecution": RecordExecution}
NODE_DISPLAY_NAME_MAPPINGS = {"ComfyGalleryRecordExecution": "Record Execution for Gallery"}
