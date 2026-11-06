/* Real-browser geometry and visual-state regressions; see verify-web-responsive.cjs
 * for the isolated fixture server contract and optional environment settings. */
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { baseUrl, mediaRows, loadPlaywright, installFixtureRoutes } = require("./verify-web-responsive.cjs");

async function overlayGeometry(page) {
  return page.evaluate(() => {
    const rect = (selector) => {
      const box = document.querySelector(selector).getBoundingClientRect();
      return { x: box.x, y: box.y, width: box.width, height: box.height, right: box.right, bottom: box.bottom };
    };
    const style = (selector) => {
      const computed = getComputedStyle(document.querySelector(selector));
      return { background: computed.backgroundColor, color: computed.color, border: computed.borderTopColor, size: parseFloat(computed.fontSize), weight: computed.fontWeight };
    };
    const overlay = document.querySelector(".media-quick-view");
    return {
      dialog: rect(".media-quick-view"), sidebar: rect(".media-quick-view-information"),
      favorite: style(".media-action-toolbar .media-favorite-button"),
      rating: style('.media-action-toolbar .media-content-rating-option[aria-pressed="true"]'),
      trash: style(".media-action-toolbar .media-trash-button"),
      heading: style(".media-quick-view-field h3"), value: style(".media-quick-view-prompt-id"),
      overflow: overlay.scrollWidth > overlay.clientWidth,
    };
  });
}

function overlayErrors(geometry, width, height) {
  const errors = [];
  if (width >= 3000) {
    if (geometry.dialog.width < width * .75) errors.push("4K dialog too narrow");
    if (geometry.dialog.height < height * .85) errors.push("4K dialog too short");
    if (geometry.sidebar.width < 560) errors.push("4K information too narrow");
  }
  if (width >= 1000 && width <= 1728 && (geometry.sidebar.width < 320 || geometry.sidebar.width > 450)) errors.push("HiDPI information outside usable width");
  if (geometry.overflow || geometry.dialog.x < 0 || geometry.dialog.right > width + 1 || geometry.dialog.bottom > height + 1) errors.push("dialog overflow");
  if (geometry.value.size < geometry.heading.size * 1.25) errors.push("metadata hierarchy too weak");
  if (geometry.favorite.background.startsWith("rgba") || geometry.rating.background.startsWith("rgba")) errors.push("selected state lacks solid fill");
  if (geometry.trash.background !== "rgba(0, 0, 0, 0)") errors.push("default Trash looks selected");
  return errors;
}

async function runOverlayChecks(browser) {
  const failures = [];
  for (const [width, height, dpr] of [[1280, 800, 2], [1440, 900, 2], [1728, 1117, 2], [1920, 1080, 1], [3840, 2160, 1], [390, 844, 2]]) {
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dpr, reducedMotion: "reduce" });
    try {
      await installFixtureRoutes(context);
      const page = await context.newPage();
      await page.goto(`${baseUrl}/library?view_media=media-1`);
      await page.getByRole("dialog").waitFor();
      await page.locator(".media-quick-view-prompt pre").waitFor();
      const geometry = await overlayGeometry(page);
      const errors = overlayErrors(geometry, width, height);
      console.log(JSON.stringify({ surface: "overlay", width, height, dpr, errors, geometry }));
      if (errors.length) failures.push({ width, errors });
      if (process.env.CG_BROWSER_QA_SCREENSHOTS) {
        await fs.mkdir(process.env.CG_BROWSER_QA_SCREENSHOTS, { recursive: true });
        await page.screenshot({ path: path.join(process.env.CG_BROWSER_QA_SCREENSHOTS, `overlay-${width}.png`) });
      }
      const favorite = page.getByRole("dialog").getByRole("button", { name: "Remove from favorites" });
      await favorite.hover();
      const hoveredBackground = await favorite.evaluate((element) => getComputedStyle(element).backgroundColor);
      assert.equal(hoveredBackground, geometry.favorite.background, "Hover must not erase selected favorite state");
      if (width === 1440 || width === 390) {
        await context.route("**/api/v1/media/media-1", (route) => route.fulfill({ json: { ...mediaRows[0], is_trash: true } }));
        await page.reload();
        const restore = page.getByRole("dialog").getByRole("button", { name: "Restore from Trash" });
        await restore.waitFor();
        assert.match(await restore.innerText(), /Restore/);
        assert.equal(await restore.getAttribute("aria-pressed"), null, "Restore is an action, not a toggle");
        assert.equal(await page.getByRole("dialog").evaluate((element) => element.scrollWidth > element.clientWidth), false, "Restore label must not overflow dialog");
        if (process.env.CG_BROWSER_QA_SCREENSHOTS) {
          await page.screenshot({ path: path.join(process.env.CG_BROWSER_QA_SCREENSHOTS, `overlay-${width}-restore.png`) });
        }
      }
    } finally { await context.close(); }
  }
  assert.equal(failures.length, 0, JSON.stringify(failures));
}

module.exports = { overlayGeometry, overlayErrors, runOverlayChecks };
if (require.main === module) {
  (async () => {
    const browser = await loadPlaywright().chromium.launch({ channel: process.env.CG_BROWSER_QA_CHANNEL || "chrome", headless: true });
    try { await runOverlayChecks(browser); }
    finally { await browser.close(); }
  })().catch((error) => { console.error(error); process.exitCode = 1; });
}
