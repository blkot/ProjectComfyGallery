# ComfyGallery Workflow Bridge

This ComfyUI custom-node package adds the receiver for the Gallery's **Open in
ComfyUI** button. It does not add a workflow node. After it is installed and
ComfyUI is restarted, the package listens for the Gallery's `postMessage`
protocol and loads either:

- a visual workflow with `app.loadGraphData`, or
- an API prompt with `app.loadApiJson`.

## Install

Copy the whole `comfy_gallery_workflow_bridge` directory into the ComfyUI
`custom_nodes` directory, for example:

```text
ComfyUI/custom_nodes/comfy_gallery_workflow_bridge/
  __init__.py
  js/
    workflow_bridge.js
    workflow_bridge_protocol.js
    workflow_bridge_receiver.js
```

Restart ComfyUI after copying. The browser must be opened by the Gallery tab;
the bridge intentionally ignores messages from unrelated windows.

## Optional origin allowlist

By default the opener window is the capability for this local, single-user
workflow. For a stricter policy, set an exact comma-separated origin list in
the ComfyUI tab's browser console and reload ComfyUI:

```js
localStorage.setItem(
  "comfy-gallery-workflow.allowed-origins",
  "http://localhost:5173,http://192.168.50.68:8181",
);
```

The list must contain the Gallery origin (scheme, host, and port), not the
ComfyUI URL.
