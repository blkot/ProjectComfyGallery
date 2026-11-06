# Registry and media viewer browser regressions

These checks complement Vitest: DOM-only tests cannot detect intersecting columns,
native checkbox sizing, stretched canvas text, or a visible gap between images.
They exercise the real Vite application in Chrome with synthetic API/media routes;
they do not require a production login or mutate NAS data.

## Run

Start a separate local development server:

```sh
pnpm --filter @comfy-gallery/web exec vite --host 127.0.0.1 --port 5197 --strictPort
```

In another terminal, using an environment with Playwright and Chrome available:

```sh
node scripts/verify-web-responsive.cjs
node scripts/verify-overlay-responsive.cjs
node scripts/verify-media-seek.cjs
```

Optional environment variables:

- `CG_PLAYWRIGHT_MODULE`: module name or absolute directory of an existing Playwright
  installation, when it is not resolvable from the repository.
- `CG_BROWSER_QA_BASE_URL`: local Vite URL; defaults to `http://127.0.0.1:5197`.
- `CG_BROWSER_QA_CHANNEL`: installed Chromium channel; defaults to `chrome`.
- `CG_BROWSER_QA_SCREENSHOTS`: directory for responsive-check screenshots.

Use a local development URL, not a deployed instance. All API paths are mocked;
the purpose is to validate the current working tree's frontend.

## Responsive contract

Use **CSS viewport/content width**, not physical monitor pixels, to choose layout.
A 3840px monitor can expose either a 3840px CSS viewport or a smaller logical
viewport under HiDPI/scaling. Cover 1280, 1440, 1728, 1920, 3840 and narrow layouts,
with expanded/collapsed main navigation and DPR 1/2.

Registry checks assert:

- Heatmap and usage never intersect, including long source/character names.
- Filters stay inside their labels/panel, and booleans remain compact inline controls.
- Canvas CSS dimensions and backing bitmap agree after accounting for DPR; a short
  one-row heatmap must not stretch its text to fill an arbitrary minimum height.
- No document-wide horizontal overflow.

Overlay checks assert fluid desktop size, a wider information column on large
screens, bounded dimensions on Mac-sized viewports, narrow-screen containment,
and distinct selected-versus-command action styling.

## Seek contract

The four-image fixture deliberately delays image delivery. Twelve wheel transitions
traverse the same scope repeatedly. A requestAnimationFrame sampler verifies that
after the initial image is loaded, there is no frame without a visible loaded image.
Every requested original must eventually become visible; browser exceptions fail
the check. Original request counts are reported as a diagnostic, not a claim about
production network timing.

Vitest separately exercises pending decoding, late/stale completions, failed images,
bounded warming, and action safety while the old frame is retained. A retained frame
must be visibly identified as loading/error, and must never allow Favorite/Rating/
Trash actions to silently target a different, not-yet-visible asset. Seek and Close
remain available.

## Failure baseline (2026-11-06)

- At 1280 CSS pixels with expanded navigation, a roughly369px Registry sidebar held
  a roughly560px heatmap panel, overlapping usage by about173px. Fixed select minimums
  and min-content sizing were incompatible with the allocated column.
- Generic label/input rules expanded checkbox controls and stacked their labels.
- A minimum canvas display height stretched the short backing bitmap.
- At 3840×2160, Overlay was capped at1440×1020 with a360px information column.
- A per-media keyed image presenter discarded the loaded frame before the next
  original was ready. Metadata cache hits alone did not guarantee a decoded frame.

Keep regression tests at these browser/presentation seams rather than asserting
particular CSS text or increasing preload scope to mask loading gaps.
