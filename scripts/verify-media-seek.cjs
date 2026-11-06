/* Four-image wheel-navigation regression with deliberately slow media delivery.
 * Uses isolated fixtures only. Start Vite on 5197; see verify-web-responsive.cjs.
 */
const assert = require("node:assert/strict");
const { baseUrl, loadPlaywright, installFixtureRoutes } = require("./verify-web-responsive.cjs");

async function runSeekChecks(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  try {
    await installFixtureRoutes(context);
    let originalsRequested = 0;
    await context.route("**/qa-media/**", async (route) => {
      const original = route.request().url().endsWith("/original");
      if (original) originalsRequested++;
      await new Promise((resolve) => setTimeout(resolve, original ? 180 : 90));
      const index = Number(new URL(route.request().url()).pathname.split("/")[2]);
      const color = ["#8badae", "#c5ad70", "#91aa96", "#aa8990"][index];
      await route.fulfill({ contentType: "image/svg+xml", body: `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1536"><path fill="${color}" d="M0 0h1024v1536H0z"/><path fill="#45554e" d="M0 1100 500 240 1024 1100v436H0z"/></svg>` });
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`${baseUrl}/library?view_media=media-1`);
    await page.getByRole("dialog").waitFor();
    await page.evaluate(() => {
      window.qaVisibleMedia = (expectedSrc) => {
        const stage = document.querySelector(".media-quick-view-stage");
        if (!stage) return false;
        return [...stage.querySelectorAll("img")].some((image) => {
          if (!image.complete || !image.naturalWidth || (expectedSrc && !image.src.endsWith(expectedSrc))) return false;
          for (let node = image; node && node !== stage; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0 || node.hidden) return false;
          }
          const box = image.getBoundingClientRect();
          return box.width > 0 && box.height > 0;
        });
      };
    });
    await page.waitForFunction(() => window.qaVisibleMedia("/qa-media/0/original"));
    await page.evaluate(() => {
      window.qaBlankFrames = [];
      window.qaUnsafeFrames = [];
      window.qaFrameCount = 0;
      window.qaSampling = true;
      function sample() {
        if (!window.qaSampling) return;
        window.qaFrameCount++;
        if (!window.qaVisibleMedia()) window.qaBlankFrames.push({ time: performance.now(), href: location.href });
        const pending = document.querySelector('.media-image-stage[data-pending="true"]');
        const actions = document.querySelector(".media-quick-view-actions");
        if (pending && actions && (!actions.disabled || !actions.inert)) window.qaUnsafeFrames.push(location.href);
        requestAnimationFrame(sample);
      }
      requestAnimationFrame(sample);
    });
    let current = 1;
    for (const target of [2, 3, 4, 3, 2, 1, 2, 3, 4, 3, 2, 1]) {
      // Give each gesture its own wheel-throttle window, like deliberate browsing.
      await page.waitForTimeout(370);
      await page.locator(".media-quick-view-stage").hover();
      await page.mouse.wheel(0, target > current ? 100 : -100);
      await page.waitForURL((url) => url.searchParams.get("view_media") === `media-${target}`);
      await page.waitForFunction((index) => window.qaVisibleMedia(`/qa-media/${index}/original`), target - 1);
      current = target;
    }
    const samples = await page.evaluate(() => {
      window.qaSampling = false;
      return { sampledFrames: window.qaFrameCount, blankFrames: window.qaBlankFrames, unsafeActionFrames: window.qaUnsafeFrames };
    });
    console.log(JSON.stringify({ surface: "media-seek", transitions: 12, originalsRequested, ...samples, errors }));
    assert.deepEqual(errors, [], "Unexpected browser error during seek");
    assert.equal(samples.blankFrames.length, 0, "Seeking exposed a blank stage between loaded images");
    assert.equal(samples.unsafeActionFrames.length, 0, "Actions were enabled while an old image was retained");
  } finally { await context.close(); }
}

module.exports = { runSeekChecks };
if (require.main === module) {
  (async () => {
    const browser = await loadPlaywright().chromium.launch({ channel: process.env.CG_BROWSER_QA_CHANNEL || "chrome", headless: true });
    try { await runSeekChecks(browser); }
    finally { await browser.close(); }
  })().catch((error) => { console.error(error); process.exitCode = 1; });
}
