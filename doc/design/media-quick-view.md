# Source-preserving media quick view

**Status:** Core quick view implemented in rc.43. Responsive and frame-stability
refinements are frontend-only changes; deploy them after local verification.

## Interaction

- Library and Prompt Registry usage cards open a shared, lightweight modal.
  The source route remains mounted; its filters, selection and heatmap state stay
  intact. Modified clicks still open the full record in a new tab.
- The modal displays original images or normal video playback with sound controls,
  not a thumbnail as the final asset. It preloads the immediate neighbors only.
  Image switching retains the last loaded frame until the requested original is
  decoded; a visible loading/error notice and disabled actions prevent editing an
  asset that does not yet match the displayed frame. Warming is bounded rather
  than expanding downloads to the entire filtered scope.
- Its toolbar is shared with full detail: Favorite star, N/R rating, Vision Pro
  spatial preference, download original, slideshow from here, Civitai, Trash/Restore.
  Permanent deletion is not added. Icons retain labels and tooltips.
  Selected Favorite/Rating use solid muted fills. Trash is a neutral outline command
  with a danger hover, not a selected toggle; trashed media offers a labeled Restore
  command. Pending/error/focus states remain distinct.
- Prompt ID and Character LoRA are prominent. The formatted LoRA list is collapsed
  by default. Positive Prompt comes exclusively from the corresponding Registry
  entry and has a copy button. Missing ID, unregistered ID, empty prompt and request
  failure are distinct states; embedded prompt text is not a silent fallback.
- Escape, the close button and clicking the backdrop close the modal. Arrow keys
  seek, F toggles favorite, N toggles rating. Wheel and middle-click apply only in
  the media stage; inputs, buttons, links and native video controls retain their
  own behavior. Native dialog focus trapping, background scroll lock and reduced
  motion are supported.
- Modal and information-column sizing follow the available CSS viewport. A wide
  desktop gets a larger media canvas and text column; Mac HiDPI logical viewports
  retain compact proportions. Metadata sections distinguish their small labels,
  prominent identifiers and readable prompt body without nested input-like boxes.

## URL and source scope

| Surface | URL | Navigation scope |
| --- | --- | --- |
| Library overlay | `/library?...&view_media=<id>` | Current Library filter/sort, across pages |
| Prompt usage overlay | `/registries/prompts?prompt_id=...&view_media=<id>` | Same prompt and usage group order, across pages |
| Full record | `/library/<id>?return_to=...` | Inherits the originating source |

Opening pushes one history entry. Seeking replaces that entry, so browser Back
closes the modal instead of replaying every viewed asset. A directly loaded overlay
URL closes in place rather than navigating out of the application. Only same-origin
Library/Prompt Registry source paths are accepted as return destinations.

Prompt usage is grouped on the server **before** pagination: preferred character
first, remaining character names alphabetically, undefined last; newest-first with
an ID tie-breaker within a group. `preferred_character_lora` prioritizes a group;
`character_lora` is an actual filter. Heatmap count filters continue to affect the
heatmap only; they do not silently narrow the visible usage list. Overlay navigation
follows that visible usage scope, including its Trash/nonfavorite records.

Slideshow uses the same source scope and returns to the overlay at its last slide.
Playlists are bounded to 2,000 records, starting exactly at the selected media even
when its position exceeds 2,000. The selected start is pinned before shuffling.
Civitai preparation returns directly to the originating overlay.

## Closing and mutations

Closing targets the last viewed media, not the originally opened card. The target
page is prefetched while seeking. On close, revalidate the immutable media ID and
refresh that page in-place; concurrent imports can shift offsets. This background
read does not unmount the source or clear its cached grid. Library uses `offset`;
Prompt usage uses `usage_offset`. `return_media` identifies the focused card.

If favorite/rating/Trash changes remove the current media from its scope, keep it
open and allow undo or seeking to a known neighbor. Closing chooses a surviving
neighbor, clamps an emptied last page, or shows the empty source. Network failures
offer Retry without discarding the source. Changing the source while restoration
is pending cancels the old navigation. Usage cards retain a prominent last-viewed
outline distinct from hover or multi-selection.

## Implementation boundaries

- `media-browse.ts`: source scope, safe return URLs, page and action URLs.
- `use-media-overlay.ts`: history, navigation query, prefetch and restoration.
- `MediaQuickView`: media rendering, metadata, native modal and local input handling.
- `MediaActionToolbar`: shared record mutations/actions; mutation caches update the
  mounted source. Heatmap refresh is deferred until close.
- Prompt usage lookup/navigation/slideshow share backend ordering. No migration or
  new asset-processing worker is required. Legacy unindexed workflow fallback is
  retained; fully indexed requests use SQL pagination/ranking.

## Verification

Automated coverage includes source DOM/local-state retention, push/replace/Back,
deep links, filtered cross-page seek, scope-removing mutations, empty/out-of-range
pages, retry, origin-preserving full detail/slideshow/Civitai, strict Registry prompt
copy, keyboard/mouse isolation and playback cleanup. Backend tests cover boundaries,
all Library sort modes, >2,000-record starts and legacy unindexed prompt evidence.

Chrome visual/interaction QA uses isolated synthetic API fixtures: desktop and
390px-wide layouts, native dialog, Library 48→49 page transition and focus return,
Prompt usage Back/close and focus outline, consistent separate card badges.
Production/NAS verification is a separate deployment step.

For repeatable responsive and wheel-seek checks, see
[Frontend browser regressions](../development/frontend-visual-regressions.md).
