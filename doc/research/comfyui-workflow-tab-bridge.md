# Opening a gallery workflow in a ComfyUI tab

**Status:** Implemented in the Gallery and ComfyUI bridge package
**Date:** 2026-08-17

## Conclusion

The feature is feasible, but `BroadcastChannel` alone is not the right bridge
for the current deployment. The browser only delivers a broadcast to channel
objects with the same channel name **and the same storage key**. In practice,
Gallery and a separately hosted ComfyUI page have different origins, so a
channel created by one page cannot reach the other. See the [HTML Standard
BroadcastChannel algorithm](https://html.spec.whatwg.org/multipage/web-messaging.html#broadcasting-to-other-browsing-contexts)
(especially the equal-storage-key destination check).

There is also no generic ComfyUI listener that would interpret an arbitrary
channel message. ComfyUI must opt in through a small JavaScript extension. The
official extension mechanism loads JavaScript from a custom node's
`WEB_DIRECTORY` and registers it with `app.registerExtension` ([ComfyUI
extension documentation](https://docs.comfy.org/custom-nodes/js/javascript_overview)).

The implemented design is therefore:

1. Gallery opens or reuses a named ComfyUI tab from a user-initiated click.
2. Gallery and the ComfyUI extension perform a small `postMessage` handshake.
3. Gallery sends the already authenticated workflow JSON to that tab.
4. The extension validates the opener/origin and loads the visual workflow with
   ComfyUI's `app.loadGraphData` API; an API-format prompt falls back to
   `app.loadApiJson`.

The receiver is packaged at
[`integrations/comfyui/comfy_gallery_workflow_bridge`](../../integrations/comfyui/comfy_gallery_workflow_bridge/README.md).
It is deliberately a standalone ComfyUI custom-node package: it contributes no
execution nodes and only registers a web extension.

`BroadcastChannel` can still be useful for coordination between multiple
Gallery tabs, or if both applications are deliberately reverse-proxied under
the same origin and the ComfyUI extension listens on the channel. It should not
be the cross-origin transport in the current setup.

## Evidence in this repository

The Gallery already exposes the data needed for the hand-off:

- Media detail renders [`WorkflowInspector`](../../apps/web/src/components/workflow-inspector.tsx),
  which calls `/api/v1/media/{id}/workflow` and loads
  `/api/v1/media/{id}/workflow/raw` on demand.
- The raw response contains both `visual_workflow` and `api_prompt` in
  [`workflows.py`](../../apps/api/src/comfy_gallery_api/routes/workflows.py)
  and [`media_schemas.py`](../../apps/api/src/comfy_gallery_api/media_schemas.py).
- The repository intentionally keeps the configured ComfyUI URL as operational
  configuration and does not return it to browsers ([deployment and security
  contract](../operations/deployment-and-security.md#configuration)).
  The browser feature will therefore need an explicit, non-secret ComfyUI UI
  origin setting (or a deliberately scoped configuration endpoint).

The existing client contract also says that captured input assets should use
the Gallery's authenticated content URL rather than call ComfyUI directly
  ([client API changelog](../interfaces/client-api-changelog.md#unreleased-captured-workflow-input-media)).
That rule is about captured media, not the proposed workflow hand-off, but it is
another reason to send preserved workflow data through the Gallery instead of
making the ComfyUI tab reach into Gallery or ComfyUI storage on its own.

## What ComfyUI can load

ComfyUI documents workflows as JSON that can be saved and reopened ([workflow
documentation](https://docs.comfy.org/basic-concepts/workflow) and [first
generation guide](https://docs.comfy.org/get_started/first_generation)). Its
frontend app exposes `loadGraphData` and `graphToPrompt`; the official object
reference also documents the visual workflow shape (`nodes`, `links`, view
state, and so on) ([Comfy objects](https://docs.comfy.org/custom-nodes/js/javascript_objects_and_hijacking)).
The current frontend source contains the related `loadGraphData` and
`loadApiJson` paths ([app.ts](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/scripts/app.ts)).

The two stored representations are not interchangeable:

- `visual_workflow` preserves the node graph and canvas-oriented data and should
  be the primary payload for opening the editor.
- `api_prompt` is the execution/API representation (node IDs mapped to
  `class_type` and `inputs`); use it only as a fallback when no visual workflow
  exists. ComfyUI's API documentation describes this as the format accepted for
  execution ([Cloud API workflow format](https://docs.comfy.org/development/cloud/overview)).

## Transport options

| Option | Works with separate Gallery/ComfyUI origins? | Assessment |
| --- | --- | --- |
| `BroadcastChannel` directly | No | Same name is insufficient; the storage-key requirement blocks delivery. |
| `BroadcastChannel` after same-origin reverse proxying | Yes, technically | Still requires a ComfyUI listener/extension and couples deployment topology. |
| `window.postMessage` to a Gallery-opened/named tab | Yes | Recommended. Cross-document messaging is designed for different origins; use an exact `targetOrigin` and validate `event.origin` ([HTML Standard security guidance](https://html.spec.whatwg.org/multipage/web-messaging.html#authors)). |
| URL query/hash containing workflow JSON | Not recommended | No documented ComfyUI deep-link contract was found; it leaks data into browser history/logs and has URL-size limits. |
| Short-lived hand-off token | Yes | Strongest isolation, but requires a small Gallery endpoint and a ComfyUI extension fetch path/CORS policy. |

An independently opened ComfyUI tab cannot be discovered by the Gallery. A
`postMessage` call requires a live `WindowProxy`, so the reliable UX is a button
that synchronously opens/reuses a named tab (`window.open`), then waits for the
extension's ready message. Popup blocking and a closed tab should be surfaced as
an actionable error.

## Implemented protocol

Use a versioned, one-request protocol rather than a permanent global channel:

```text
Gallery click
  └─ window.open(comfyUiOrigin, "comfyui-workflow")
       └─ ComfyUI extension -> opener: { type: "comfy-gallery-workflow-ready", version: 1 }
Gallery fetches /api/v1/media/{id}/workflow/raw
  └─ opener.postMessage(
       { type: "comfy-gallery-open-workflow", version: 1, requestId, mediaId,
         representation: "visual_workflow", workflow },
       exactComfyUiOrigin)
       └─ ComfyUI extension validates opener/origin/schema/size/request id
            └─ app.loadGraphData(workflow)
                 └─ opener <- { type: "comfy-gallery-open-workflow-ack", requestId, ok }
```

Implementation details:

- Call `window.open` directly in the button handler before any asynchronous
  fetch, so popup blockers do not reject the tab.
- Use the configured ComfyUI origin as `targetOrigin`; never use `*` for workflow
  data. The HTML Standard specifically warns against wildcard targets for
  confidential messages and requires receiver-side `event.origin` and payload
  validation.
- Send only the selected workflow representation, not `raw_metadata`, bearer
  tokens, or unrelated evidence. The implementation uses a request ID, bounded
  retry deduplication, a short timeout, and an acknowledgement/error response.
- If the browser should not carry the full JSON, add a short-lived, one-time
  Gallery hand-off token. That is the only part that would require a new backend
  endpoint; the existing raw workflow route is sufficient for a direct
  `postMessage` payload.

## Scope delivered

This is a cross-application integration, not a Gallery-frontend-only change.
The smallest useful slice is:

- **Gallery frontend:** button, ComfyUI UI-origin setting, named-tab lifecycle,
  raw-workflow fetch, handshake, timeout, and error states.
- **ComfyUI side:** [`comfy_gallery_workflow_bridge`](../../integrations/comfyui/comfy_gallery_workflow_bridge/README.md),
  a small custom-node JavaScript extension that listens for the handshake,
  validates the Gallery opener/origin, deduplicates retries, and invokes the
  supported app loader.
- **Backend:** no change if the Gallery sends the authenticated raw JSON
  directly; add a short-lived hand-off endpoint only if we choose token-based
  transfer or need to expose a sanitized UI-origin configuration.

The implementation replaces the proposed cross-origin `BroadcastChannel`
transport with `postMessage` plus the explicit ComfyUI extension. `BroadcastChannel`
remains an optional same-origin fallback for future multi-tab coordination.
