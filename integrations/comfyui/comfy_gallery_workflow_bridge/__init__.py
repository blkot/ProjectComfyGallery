"""ComfyUI web extension for receiving workflows from ComfyGallery."""

WEB_DIRECTORY = "./js"

# This package intentionally contributes no execution nodes.  The web directory
# is registered by ComfyUI when the custom node package is loaded.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
