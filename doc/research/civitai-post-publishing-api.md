# Civitai post publishing from ComfyGallery

**Status:** Research complete; no integration implemented
**Date:** 2026-08-21
**Source snapshots:** Civitai developer docs
[`730497a`](https://github.com/civitai/civitai-developer-docs/tree/730497a1ce70bfea1f7ecbf20e15edad61e7dbd4)
and Civitai MCP server
[`c40d8c0`](https://github.com/civitai/civitai-mcp-server/tree/c40d8c02b264152ba6f40d7cac436af5c04c332e)

## Conclusion

Yes. Civitai now provides an official, hosted write interface at
`https://mcp.civitai.com/mcp`. Its `create_post` tool can create a draft or
publish an image post, accepting each image either as a Civitai upload UUID or
as a remote URL that the MCP server fetches and uploads automatically. It uses
Streamable HTTP/JSON-RPC, not a conventional `POST /api/v1/posts` REST endpoint.
The official REST reference still exposes browsing endpoints and does not list
a public REST post-creation route
([REST reference index](https://github.com/civitai/civitai-developer-docs/blob/730497a1ce70bfea1f7ecbf20e15edad61e7dbd4/site/reference/index.md)).

This can remove the user's manual **download from ComfyGallery, then upload in
the Civitai browser** workflow. It is not zero-copy: Civitai must still ingest
and store the media bytes.

For ComfyGallery's current private-LAN deployment, a raw URL such as
`http://192.168.50.68/...` cannot be passed to the hosted service. The official
MCP server rejects loopback and RFC1918 destinations, including
`192.168.0.0/16`, as an SSRF defense
([safe URL fetcher](https://github.com/civitai/civitai-mcp-server/blob/c40d8c02b264152ba6f40d7cac436af5c04c332e/src/lib/safe-fetch.ts)).
The practical MVP is therefore a **ComfyGallery backend-to-Civitai upload**:
read the already-managed image, call `upload_image` with base64, then call
`create_post` with the returned UUID. No browser download or local re-upload is
required.

## Supported contract

| Capability | Current evidence | Assessment |
| --- | --- | --- |
| Create and optionally publish a post | Official `create_post` tool; atomic create + ordered attachments + optional publish | Supported for image posts |
| Authenticate a write | Bearer Civitai API key; account must be onboarded and not muted; token needs `MediaWrite` (or Full) | Supported |
| Attach an already uploaded item | `images[].uuid` is the pre-upload UUID | Supported |
| Supply a remote image URL | `images[].url` is fetched and uploaded before post creation | Supported, subject to reachability, SSRF, and size limits |
| Upload local bytes | `upload_image` accepts a URL or base64 and returns a UUID | Supported for images |
| Attach image, video, or audio type | The live schema and source expose `images[].type = image | video | audio` | Representation exists, but upload/publishing support beyond images is not sufficiently documented to treat as production-ready |
| Direct REST `POST /api/v1/posts` | Absent from the official REST reference | Do not assume it exists as a public contract |

The hosted endpoint, bearer-key setup, and write behavior are documented in
the [official MCP overview](https://github.com/civitai/civitai-developer-docs/blob/730497a1ce70bfea1f7ecbf20e15edad61e7dbd4/site/mcp/index.md).
The [official MCP tool reference](https://github.com/civitai/civitai-developer-docs/blob/730497a1ce70bfea1f7ecbf20e15edad61e7dbd4/site/mcp/tools.md)
describes `create_post` as an atomic image-post operation, with images accepted
by UUID or URL, and describes `upload_image` as URL/base64 to a presigned upload.
`MediaWrite` explicitly grants media upload and post creation
([OAuth scopes](https://github.com/civitai/civitai-developer-docs/blob/730497a1ce70bfea1f7ecbf20e15edad61e7dbd4/site/oauth/scopes.md)).

## What happens to the media

The supported URL flow is not a permanent hotlink:

1. `create_post` resolves a URL by calling the MCP server's `uploadImage`
   helper.
2. The helper downloads the bytes, obtains an upload UUID and presigned storage
   URL from Civitai, then `PUT`s the bytes to that storage URL.
3. `post.createWithImages` receives the upload UUID in its attachment `url`
   field and returns the post plus final numeric image IDs.

This behavior is visible in the official
[`create_post` implementation](https://github.com/civitai/civitai-mcp-server/blob/c40d8c02b264152ba6f40d7cac436af5c04c332e/src/tools/posts.ts)
and
[`upload_image` implementation](https://github.com/civitai/civitai-mcp-server/blob/c40d8c02b264152ba6f40d7cac436af5c04c332e/src/tools/images.ts).
A ComfyGallery integration should use the hosted MCP abstraction instead of
calling Civitai's internal tRPC procedures directly. The tRPC names are an
implementation detail behind the official MCP contract.

## Private NAS implications

### Recommended MVP: backend byte bridge

```text
User chooses Publish in ComfyGallery
  -> ComfyGallery worker reads the existing managed image
  -> MCP upload_image { data: <base64>, contentType }
  <- upload UUID
  -> MCP create_post { images: [{ uuid }], title, detail, tags, publish }
  <- Civitai post ID, image IDs, and public post URL
  -> ComfyGallery stores the remote IDs and outcome
```

This keeps the Civitai bearer token in backend secrets and does not expose the
NAS or embed credentials in the web frontend. It does transfer the file once
from ComfyGallery to Civitai, which is unavoidable for a hosted Civitai asset.

The official MCP implementation defaults URL/base64 image uploads to 10 MiB
and caps its HTTP request body at 25 MiB; Civitai does not publish the hosted
deployment's effective configuration separately. Base64 adds roughly one-third
overhead. The project's usual several-megabyte images should fit under the
documented defaults, but ComfyGallery must check the byte size before queuing
and surface an explicit unsupported-size error rather than retrying
indefinitely. The MCP tool catalog does not publish a stable per-endpoint rate
limit; 429 and 5xx responses should use bounded exponential backoff
([Civitai error guidance](https://github.com/civitai/civitai-developer-docs/blob/730497a1ce70bfea1f7ecbf20e15edad61e7dbd4/site/guide/errors.md)).

### Optional later path: short-lived public URL

For one-call URL publishing, ComfyGallery could expose a narrowly scoped,
short-lived public HTTPS URL for one asset. It would need public DNS and ingress,
an unguessable signed token in the URL, a short expiry, a strict byte limit, and
no dependence on Gallery cookies or bearer headers. The hosted MCP call does
not provide a way to send ComfyGallery authentication headers when fetching the
URL. Exposing the NAS's general media route is not acceptable.

Self-hosting the unmodified Civitai MCP server on the NAS does not make a
private URL work: its URL fetcher still rejects private IP addresses. A local
fork could remove that defense, but then ComfyGallery would own a security- and
compatibility-sensitive divergence for little benefit over sending base64.

## Image and video boundary

Images are the documented supported write path. The official tool reference
calls `create_post` an image-post tool, and `upload_image` only documents image
input and probes PNG, JPEG, GIF, and WebP.

The live `create_post` schema and its official source do allow attachment types
`image`, `video`, and `audio`, and Civitai's read API also exposes those media
types. That is not enough to prove a supported video-upload workflow: there is
no documented `upload_video` or generic media uploader, no MCP video size or
transcoding contract, and the documented 10 MiB helper is image-oriented.
ComfyGallery should therefore ship image publishing first and gate video/audio
until a draft upload has been validated against the live service or Civitai
publishes the contract.

For a user-confirmed video fallback, Civitai's official
[Post Intent System](https://github.com/civitai/civitai/wiki/Post-Intent-System)
can open a prefilled Civitai post form from an absolute public URL. It documents
PNG/JPEG/WebP images and MP4/WebM videos, but it is interactive rather than a
headless create-post API. A plain `http://192.168.x.x` media URL is not a safe
integration contract: Civitai's hosted services cannot route to it, and an
HTTPS Civitai page may be prevented from fetching it by browser mixed-content
or private-network controls.

## Recommended ComfyGallery product boundary

If implemented, keep this as a backend integration and background job:

- Store a Civitai API key only in the backend secret configuration for the
  single-user MVP. If this becomes multi-user, use Civitai OAuth and request the
  narrow `MediaWrite` scope instead of collecting users' personal keys.
- Require an explicit user publish action; default to a Civitai draft until the
  mapping and moderation behavior have been proven.
- Persist provider, local media ID, upload UUID, remote post ID, remote image
  IDs, URL, state, error, and timestamps. This prevents blind retries after an
  ambiguous timeout from creating duplicate posts.
- Treat Civitai moderation/onboarding failures as terminal user-action errors,
  not worker-transient failures.
- Do not call `post.createWithImages`, `/api/trpc/*`, or the presign route
  directly from ComfyGallery. Use `create_post` and `upload_image` so Civitai's
  hosted compatibility layer owns those internal details.
- Limit the first release to supported image MIME types and sizes. Add videos
  only after a real draft round-trip establishes their upload, scan,
  publication, and playback behavior.

## Stability note

The hosted MCP server and its developer documentation are first-party Civitai
projects, so this is a supported integration surface rather than reverse
engineering a browser request. The server advertises live schemas through
MCP `tools/list`; ComfyGallery should validate required fields at startup or in
an integration health check and fail closed if the contract changes. Content
still passes through Civitai account permissions, onboarding, scanning,
moderation, and operational rate limiting.
