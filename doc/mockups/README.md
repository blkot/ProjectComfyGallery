# Library & Detail Prototype

A static, self-contained interaction prototype for the Media Library redesign. It
exists to settle two questions before implementation:

1. whether the library should keep server pagination or move to masonry, and
2. whether Media Detail should open as an overlay while keeping the library mounted.

Open [`library-detail.html`](library-detail.html) directly in a browser. No build,
server, backend, or network access is required.

## What to try

- **Layout toggle** (Grid / Masonry). Masonry keeps pagination but fills columns
  vertically; the inline note calls out the timeline trade-off.
- **Card click** opens the detail overlay. The URL updates to `#media=<n>`.
- **← / →** seeks across the whole filtered population, including page boundaries.
  The toolbar shows `position / total` and the current page.
- **Close** (X, Esc, or clicking outside) returns to the **last viewed item**, not
  the opening card: the grid jumps to that page, scrolls the card into view, and
  flashes a highlight. A toast confirms the destination.
- **Info / Evaluate** tabs show that the overlay can host both the quick view and
  the evaluation surface.
- **Favorite**, **Copy prompt**, and the evaluation sliders are local-state only.

## Prototype limits

- 1,248 items are generated deterministically; only 12 render per page to keep the
  demo light. The real library uses 48.
- Artwork is generated SVG; no project media is embedded.
- No API, persistence, selection, or real evaluation. Colors/typography are
  placeholders for the pending visual direction, not a final skin.
- Desktop-first; the narrow layout stacks media above the inspector.

## Screenshots

- [Grid library](screenshots/library-grid.png)
- [Detail overlay](screenshots/library-detail.png)
- [Masonry variant](screenshots/library-masonry.png)
- [Detail on a narrow viewport](screenshots/library-detail-mobile.png)
