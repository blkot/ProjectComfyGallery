# Legacy Spatial Preference Backend Guide

**Status:** Superseded by backend release `0.1.0-rc.11`

This file is retained only so old handoff links do not break. Its former proposal
used the image-era `spatial_view_preferred` name and coupled spatial preference to
Favorite. Those semantics are no longer authoritative.

Current clients must use:

```http
PUT /api/v1/media/{media_id}/playback-preference
Content-Type: application/json

{"prefer_spatial_playback": true}
```

Current media projections expose independent fields:

```json
{
  "favorite": false,
  "prefer_spatial_playback": true,
  "spatial_available": false
}
```

- `favorite` is user-owned and independent.
- `prefer_spatial_playback` is user intent shared by images and videos.
- `spatial_available` is read-only availability of an active ready stored
  spatial-video variant and remains false for runtime spatial images.
- Deprecated `spatial_view_preferred` and `/spatial-preference` aliases exist only
  for compatibility.

The backend does not couple these fields. The XR client deliberately composes two
writes for runtime spatial-image actions: Make Spatial/Enable Cached Spatial sets
Favorite and playback preference to true, while Disable Spatial sets both false.
Spatial-video playback controls continue to change only playback preference.

Authoritative references:

- [`../doc/decisions/0011-imported-media-variants.md`](../doc/decisions/0011-imported-media-variants.md)
- [`../doc/interfaces/client-api-changelog.md`](../doc/interfaces/client-api-changelog.md)
- [`api-and-media-contract.md`](api-and-media-contract.md)
