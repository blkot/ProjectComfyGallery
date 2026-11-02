# Optional display fields for Xanta Save & Upload

This patch targets the standalone Windows `ComfyUI-Xanta-Utils/nodes.py`.
It is not an additional custom node. From a compatible copy of Xanta Utils,
check with `git apply --check /path/to/nodes.patch` before applying. Back up
the original file. Reload ComfyUI when ready, then refresh the browser so the
existing XantaSaveAndUpload node exposes the new optional inputs.

See [field semantics, wiring and history recovery](../../../doc/design/workflow-display-overrides.md).
The existing upload protocol and token configuration do not change. If old
executions are needed, preserve their verified evidence before restarting ComfyUI.
