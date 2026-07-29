# Domain Documentation

This is a multi-context repository. Start at `CONTEXT-MAP.md`, then read only the
main, mobile, or XR context relevant to the current role.

## Before exploring

Read:

1. `CONTEXT-MAP.md`.
2. The relevant context's documents linked by the map.
3. Relevant system-wide ADRs under `doc/decisions/`.
4. The complete GitHub tracking issue and comments when the task is coordinated
   across sessions.

For spatial-video work, the shared sources are:

- [`#2 — Tracking: spatial video variants across backend and XR`](https://github.com/blkot/ProjectComfyGallery/issues/2)
- `doc/development/spatial-video-variant-backend-update.md`

## Context boundaries

- **Main:** repository root excluding `mobile/` and `XR/`; owns backend, web,
  storage, processing, and deployment.
- **Mobile:** `mobile/`; owns native iPhone/iPad behavior.
- **XR:** `XR/`; owns native Vision Pro behavior and runtime spatial-image
  presentation.

Do not treat an XR runtime-generated spatial image as a stored backend variant.
Do not make the Gallery backend responsible for external spatial-video generation.

## Vocabulary

Use terms as defined in `doc/glossary.md` and context-specific requirements.
For the spatial-video feature:

- **Original:** the immutable ComfyUI-generated video represented by `MediaAsset`.
- **Spatial-video variant:** a validated Apple spatial MV-HEVC file attached to the
  same logical `Media`.
- **Spatial availability:** system-owned video state derived from an active, ready
  spatial-video variant.
- **Spatial playback preference:** user-owned intent shared by image and video.
- **Runtime spatial image:** an XR-owned, in-memory RealityKit presentation; not a
  stored file variant.

If a session needs a new term or changes one of these meanings, update the
appropriate domain document and add or supersede an ADR when the boundary changes.

## ADR conflicts

Surface conflicts instead of silently overriding them. ADRs are append-only:
supersede a decision with a new ADR rather than rewriting its history.
