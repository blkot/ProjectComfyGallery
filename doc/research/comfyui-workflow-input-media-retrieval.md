# ComfyUI workflow input-media retrieval

Status: implementation research for GitHub issue #12  
Source snapshot: ComfyUI `cbbc9dab` and ComfyUI Frontend `e544b2ad`, both
current on 2026-08-09. Links below are pinned to those commits.

## Conclusion

Comfy Gallery can capture built-in ComfyUI image and video inputs immediately
after importing a generated media item. The safe legacy request is:

```http
GET /view?filename=<basename>&subfolder=<relative-subfolder>&type=input
```

The response without `preview` or `channel` is the current file's original
bytes. Comfy Gallery should stream those bytes into its own immutable,
SHA-256-deduplicated input-asset store and thereafter serve the stored copy.
`/view` is a live lookup, not historical provenance: it has no execution or
prompt identifier, so a missing, renamed, or replaced ComfyUI file cannot be
recovered as the version used by an earlier generation.

## Current `/view` contract

- `filename` is required. For legacy path references, `type` selects only
  `input`, `output`, or `temp`; if omitted it defaults to `output`. `subfolder`
  is optional and is relative to the selected root. A missing file or an
  unresolved asset hash returns `404`; malformed filenames and unknown types
  return `400`; a lexically escaping subfolder returns `403`.
  [ComfyUI route](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/server.py#L516-L558)
  [directory types](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/folder_paths.py#L219-L227)
- Current asset-enabled ComfyUI may put a `blake3:...` asset hash in a
  `LoadImage` widget instead of a path. `/view?filename=blake3:...` resolves
  that hash for the request's ComfyUI user. In multi-user mode the user is
  selected with the `comfy-user` request header; otherwise it is `default`.
  Preserve the source reference, fetch it through `/view`, then still compute
  Comfy Gallery's own SHA-256 over the returned bytes.
  [asset-hash resolution](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/server.py#L521-L530)
  [user selection](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/app/user_manager.py#L36-L70)
- With neither `preview` nor `channel=rgb|a`, the handler returns an
  `aiohttp.web.FileResponse` and guesses the content type from the filename (or
  uses the asset record's content type). `preview` re-encodes images as WebP or
  JPEG, while `channel=rgb|a` returns a transformed PNG. Capture must omit those
  options to avoid altering the source bytes. Active browser content types are
  forced to download with `nosniff`; this does not replace media-type sniffing
  in Comfy Gallery.
  [response behavior](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/server.py#L558-L659)
- The route rejects a leading slash or any `..` in `filename`, reduces it to a
  basename, and applies `abspath`/`commonpath` containment to `subfolder`.
  However, its legacy-path branch does not call ComfyUI's separate
  realpath/symlink-aware containment helper. Comfy Gallery should therefore
  call only a configured ComfyUI origin, construct the query itself from parsed
  fields, reject absolute/traversing paths, decline redirects to another
  origin, and independently enforce time and byte limits.
  [route checks](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/server.py#L533-L556)
  [realpath-aware helper used elsewhere](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/folder_paths.py#L326-L370)
- `/view` does not impose an application-level response-size limit or fetch
  deadline. Those are responsibilities of the Comfy Gallery client. This is
  especially relevant for input videos.

## Built-in API-prompt shapes

ComfyUI's API prompt is an object keyed by node ID; each node has `class_type`
and `inputs`. The official example also notes that it is produced by **Export
(API)**.
[official API example](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/script_examples/basic_api_example.py#L4-L95)

The current built-in schemas imply these shapes:

```json
{
  "17": {
    "class_type": "LoadImage",
    "inputs": { "image": "references/person.png" }
  },
  "18": {
    "class_type": "LoadVideo",
    "inputs": { "file": "references/motion.mp4" }
  }
}
```

| Node | Path-bearing API input | Current built-in behavior |
| --- | --- | --- |
| `LoadImage` | `inputs.image` | Enumerates image MIME types from the input directory, resolves the value relative to the input root, and fingerprints current bytes with SHA-256 for ComfyUI execution caching. The fingerprint is not embedded as historical provenance. |
| `LoadVideo` | `inputs.file` | Enumerates video MIME types from the input directory, resolves the value relative to the input root, and fingerprints by modification time rather than hashing a potentially large file. |

Sources:
[LoadImage](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/nodes.py#L1730-L1804),
[LoadVideo](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/comfy_extras/nodes_video.py#L220-L258).

These two built-ins are reliable seed mappings, not a universal rule. Custom
nodes can use other class names, input keys, nested objects, or multiple media
values. They still require the project's semantic node registry and value
locators, with first-run suggestions based on ComfyUI node definitions and
manual correction.

## Filename conventions

The current frontend parses a media widget string as
`subfolder/filename [type]`, defaults an absent annotation to `input`, and
splits the subfolder at the last `/`.
[frontend parser](https://github.com/Comfy-Org/ComfyUI_frontend/blob/e544b2ad9011e916ac9a96288630d3871eea52b5/src/utils/imageUtil.ts#L34-L56)

The upload UI posts the file to `/upload/image` even for the generic media
upload widget, then stores the server-returned `subfolder/name` in the widget.
On filename collision, the server reuses identical bytes or selects a name such
as `name (1).ext` unless overwrite was requested; its JSON response contains
the final `name`, `subfolder`, and `type`. Therefore the embedded API-prompt
value should be treated as the authoritative live reference, not the user's
pre-upload local filename.
[frontend upload value](https://github.com/Comfy-Org/ComfyUI_frontend/blob/e544b2ad9011e916ac9a96288630d3871eea52b5/src/renderer/extensions/vueNodes/widgets/composables/useWidgetSelectActions.ts#L38-L78)
[server collision and response behavior](https://github.com/Comfy-Org/ComfyUI/blob/cbbc9dab1f03d0d9a6caa8a8be7d77a7e37e1e44/server.py#L397-L460)

Canonicalization for capture should be:

1. If the value begins with `blake3:`, send it as `filename` without attempting
   path parsing; attach a configured `comfy-user` header only when required.
2. Otherwise strip a recognized trailing ` [input]`, ` [output]`, or ` [temp]`;
   absent annotation means `input` for loader-node values.
3. Normalize separators to `/`, split at the last slash into `subfolder` and
   basename, and reject empty, absolute, NUL-containing, or traversal values.
4. Send all three query fields explicitly. In particular, never omit
   `type=input`, because `/view` itself otherwise defaults to `output`.

## Implementation implications for issue #12

1. Discover candidates from the preserved API-prompt graph first, using the
   built-in mappings above plus enabled semantic-registry mappings for custom
   nodes. Keep node ID, class type, input locator, and raw reference as evidence.
2. Resolve soon after workflow parsing. A failed resolution must not fail the
   generated-media import; retain a retryable unresolved reference with a
   reason such as `comfyui_unreachable`, `not_found`, `unsupported_media`,
   `too_large`, or `invalid_reference`.
3. Stream the untransformed response through an explicit maximum-size guard,
   sniff the actual media type, compute SHA-256, and atomically publish it into
   managed input-asset storage. Do not trust only the filename extension or
   ComfyUI's MIME guess.
4. Deduplicate immutable input assets by SHA-256 while retaining one usage link
   per generated media, workflow node, and input locator. This allows one input
   image or video to be reused by many generations without duplicate stored
   bytes.
5. Serve the captured asset from Comfy Gallery. ComfyUI is needed only during
   initial resolution or an explicit retry; later renames, replacements,
   deletion, or downtime must not affect already captured records.

## First-party limitations to preserve in the product contract

- A path reference identifies current ComfyUI storage, not the bytes used at
  execution time. Fetching immediately minimizes but cannot remove that race.
- There is no workflow-execution parameter on `/view`; retrieval cannot prove
  historical identity until Comfy Gallery has captured and hashed the bytes.
- Current built-in `LoadImage` and `LoadVideo` cover only their own input keys.
  Custom loader variants cannot be inferred safely from class-name substrings.
- A `blake3:` reference is owner-scoped in multi-user mode and can return `404`
  if requested under the wrong ComfyUI user.
- The endpoint returns current bytes without an issue-specific size ceiling or
  timeout. The resolver must be bounded and must fail without leaving a partial
  managed file.
