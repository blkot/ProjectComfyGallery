# Frontend Redesign and UI Foundation

**Status:** Proposed — awaiting the visual reference

## Scope

This document prepares a visual and structural redesign of the React web client in
`apps/web`. It covers the design foundation, the component architecture, and the
migration order. It does not change product behavior, API contracts, or route names;
those remain governed by [frontend UX](frontend-ux.md), the requirement IDs in
[requirements](../product/requirements.md), and the
[API contract](../interfaces/api-and-integrations.md).

The redesign is a re-skin **and** a re-foundation. The current interface is a single
custom stylesheet applied to large page components; a new visual language cannot be
introduced reliably without first creating reusable primitives and page-level
boundaries.

## Why now

Measured on `main` at `0.1.0-rc.34`:

| Observation | Value |
| --- | --- |
| Web source | ~19,000 lines across 62 TS/TSX files |
| Global stylesheet | 7,202 lines, 1,177 selectors, 439 distinct class strings |
| Hard-coded colors outside the token block | 129 hex literals + 79 `rgb()`/`hsl()` values |
| Breakpoints in the stylesheet | 15 distinct `max-width`/`min-width` values, 9 responsive rules |
| Page components over 1,000 lines | 3 (`library` 1,813, `model-registry` 1,439, `analysis` 1,060) |
| Shared UI primitives | none (no `ui/` layer, no component library, no Storybook) |
| Reused layout classes | 12 page headers, 52 `panel`, 34 `card`, 21 `empty-state` |
| Inline SVG icons | 21 one-off icon definitions, 17 of them in the Library page |
| Automated tests | 113 Vitest/RTL tests, `eslint` + `tsc` green |

Consequences visible in the code and the current screenshots:

1. **No visual contract.** Colors, radii, spacing, and focus rings are re-declared per
   feature. A redesign would require editing hundreds of unrelated selectors, and any
   new screen would drift again.
2. **Styling is coupled to page markup.** Class names such as `metric-card`,
   `phase-marker`, or `principle-card` encode one page's layout. The same concept
   (panel, badge, toolbar, table, dialog) is re-implemented per page.
3. **Pages are monoliths.** Filtering, selection, mutations, dialogs, pagination, and
   presentation live in one component. The Library page alone holds ~20 mutations and
   30 pieces of local state, so its layout cannot be changed without risking behavior.
4. **Iconography is ad hoc.** Icons are four-path SVGs with inconsistent stroke
   weights; there is no shared size or alignment rule.
5. **Breakpoints are feature-local.** Nine independent media queries make the shell,
   gallery, inspector, and review layout disagree at intermediate widths.
6. **The visual language has drifted.** Georgia serif headings, a lime accent, olive
   greys, and a mix of bordered and filled surfaces no longer express one system.

## Invariants

The redesign must preserve:

- Routes, URL state, and the query-parameter contract in `src/lib/media-view.ts`
  (filters, sort, offset, return anchor, `panel=evaluation`).
- The blind-review boundary (EVAL-017): no checkpoint, LoRA, workflow, collection,
  or source evidence inside the review workspace.
- Autosave, independent decisions, nullable scores, N/A, revision history, and
  reversible Trash semantics.
- Explicit selection across pagination, server-resolved "select all matching", and
  server-created collections. The redesign must not move filtering to the browser.
- Media Detail as a fixed-height workstation with an independently scrolling
  inspector, and the Info/Evaluate switch beside the filename.
- Slideshow and Photo Wall as presentation-only routes without the app shell.
- Accessibility: keyboard reachability, visible focus, non-color-only state, reduced
  motion, and chart table equivalents.
- Existing tests and their behavioral assertions. New primitives must adopt the same
  accessible names the tests query.

## Target architecture

Four layers, each only depending on the one above it:

```text
src/styles/       tokens.css (semantic variables), reset.css, base.css
src/ui/           primitives: Button, IconButton, Field, Select, Checkbox,
                  Dialog, Toast, Badge, Panel, Toolbar, PageHeader, Tabs,
                  EmptyState, DataTable, SegmentedControl, Spinner
src/patterns/     compositions: MediaCard, FilterRail, EvidenceSection,
                  InspectorTabs, ScoreControl, ResultTable, ShellNav
src/pages/        route containers: data fetching + composition only
```

- **Tokens.** One semantic set (`--surface-*`, `--text-*`, `--accent-*`, `--status-*`,
  `--space-*`, `--radius-*`, `--type-*`, `--shadow-*`, `--motion-*`, `--z-*`). No
  literal color outside `tokens.css`. Light and dark are two token scopes on `:root`,
  so a theme switch is a data attribute, not a stylesheet fork.
- **Styling.** CSS Modules co-located with each component, plus the three global
  stylesheets. Vite supports Modules natively, so this adds no dependency. Page-level
  CSS is not allowed to style another page's elements.
- **Icons.** One `Icon` registry component with a single stroke width and two sizes
  (16/20). Reuse `lucide-react` only if the team accepts one small dependency;
  otherwise keep an internal registry.
- **Layout.** One responsive model with three tiers (wide workstation ≥1280,
  compact 768–1279, narrow <768) and container queries for the gallery grid and the
  inspector. The shell owns navigation, page width, and the command/search entry.
- **Decomposition.** Each page is split into a route container plus `patterns/`
  pieces. Target: no page component over ~300 lines; mutations move into typed hooks
  such as `useLibraryMutations`.

## Migration sequence

Each phase is shippable and keeps the app green.

1. **Foundation.** Add tokens, reset, base typography, and the theme attribute. Port
   the existing palette into tokens first (no visual change) so later phases have a
   stable mapping. Exit: CSS has no literal colors outside tokens; check/tests pass.
2. **Primitives.** Build `ui/` with tests and a local `/ui` playground route (dev
   only) to review states. Exit: every primitive has keyboard and focus tests.
3. **Shell and pages frame.** Replace the sidebar/header with the new shell, page
   header, toolbar, and empty/loading/error patterns. Exit: all routes render without
   page-specific shell CSS.
4. **Library and Media Detail.** Split the 1,813-line page into `FilterRail`,
   `MediaGrid`, `SelectionBar`, `Pagination`, and mutation hooks. Rebuild the media
   card and the detail workstation on primitives. Exit: existing Library/Detail tests
   pass unchanged; return-anchor and URL behavior verified manually.
5. **Review.** Rebuild the review home and workspace layout; keep `evaluation-controls`
   behavior and autosave contract. Verify blindness with a checklist.
6. **Registries, Analysis, Operations, Imports, Jobs, Tokens, Login.** Migrate one
   page per change, deleting superseded selectors as each lands. Exit: `styles.css`
   is gone; no dead selectors remain.
7. **Hardening.** Visual regression baselines for the main routes, dark/light and
   narrow viewports, keyboard-only pass, contrast check, and a bundle-size check.

## Quality gates

- `pnpm --filter @comfy-gallery/web check` and `test` stay green at every commit.
- No new runtime dependency without an explicit decision; CSS Modules and tokens add
  none.
- Every page keeps its loading, empty, filtered-empty, degraded, and error states.
- Route-level code splitting and the 48-item server pagination remain.
- No raw workflow JSON is fetched for gallery routes.

## Decisions

Recorded 2026-11-03:

1. **Brand.** Keep the "ComfyGallery" wordmark and the `CG` mark. Replace the lime
   accent; the accent color is part of the pending visual direction.
2. **First round.** Build the UI foundation (tokens, primitives) and the new
   application shell first. Page-level replacement follows per route, so the shell
   change is the only cross-page change.
3. **Visual direction.** Supplied externally as a reference; no implementation
   starts until it is available. The three local directions below are kept only as
   fallbacks.

## Reference analysis

- [GLORIA Prompt Archive design analysis](gloria-prompt-archive-analysis.md) —
  a reference study of a prompt gallery's card grid and independent card detail,
  including its overlay-and-deep-link model, media-driven sizing, information
  order, gestures, and the trade-offs that should not be copied wholesale.

## Open decisions

1. **Visual direction.** Pending the external reference. Fallbacks if none is
   supplied: (a) *Graphite studio*: neutral near-black/graphite chrome, one cool
   accent, imagery carries all color, compact data density. (b) *Paper gallery*:
   light warm-neutral canvas with dark text and a muted ink accent, closer to a
   print contact sheet. (c) *Dual theme*: both, with the same tokens.
2. **Density.** Compact workstation density with smaller cards versus the current
   large 2:3 cards.
3. **Icon dependency.** Internal registry or `lucide-react`.
4. **Light mode.** Required, optional, or dark-only.
