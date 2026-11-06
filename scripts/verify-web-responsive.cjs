/* Browser geometry regression: run a local Vite server, then node this file.
 * All API/media requests are isolated fixtures; this never writes production data.
 * Optional: CG_PLAYWRIGHT_MODULE, CG_BROWSER_QA_BASE_URL, CG_BROWSER_QA_SCREENSHOTS.
 */
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs/promises");

const baseUrl = process.env.CG_BROWSER_QA_BASE_URL || "http://127.0.0.1:5197";
const source = "very-long-prompt-source-for-responsive-layout-testing";
const character = "Character_LoRA_with_a_long_name_and_version_suffix_v12";
const promptId = `${source} - 0007`;
const mediaRows = Array.from({ length: 4 }, (_, index) => ({
  id: `media-${index + 1}`, kind: "image", status: "ready",
  original_filename: `responsive-fixture-${index + 1}.png`,
  width: 1024, height: 1536, byte_size: 1827484, duration_seconds: null,
  detected_format: "png", mime_type: "image/png", warning_count: 0, source_count: 1,
  workflow_status: "parsed", evaluation_state: "not_started", is_trash: false,
  spatial_available: false, prefer_spatial_playback: false, spatial_view_preferred: false,
  favorite: index === 0, content_rating: index === 0 ? "nsfw" : "sfw",
  file_created_at: "2026-11-05T15:30:00Z", created_at: "2026-11-05T15:30:00Z",
  preview_url: `/qa-media/${index}/preview`, original_url: `/qa-media/${index}/original`,
  playback_url: `/qa-media/${index}/original`, character_lora: character,
  sources: [], warnings: [], model_references: [],
}));

function loadPlaywright() {
  return require(process.env.CG_PLAYWRIGHT_MODULE || "playwright");
}

function navigation(id) {
  const index = mediaRows.findIndex((media) => media.id === id);
  return { media_id: id, position: index + 1, total: mediaRows.length,
    previous_id: mediaRows[index - 1]?.id ?? null, previous_position: index > 0 ? index : null,
    next_id: mediaRows[index + 1]?.id ?? null, next_position: index + 1 < mediaRows.length ? index + 2 : null };
}

async function installFixtureRoutes(context) {
  await context.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname.endsWith("/auth/session")) body = { user: { id: "qa", username: "Responsive QA" } };
    else if (url.pathname.endsWith("/prompt-registry/sources")) body = [source];
    else if (url.pathname.endsWith("/prompt-registry/character-loras")) body = [{ name: character, media_count: 4 }];
    else if (url.pathname.endsWith("/prompt-registry/heatmap")) body = { items: [{ prompt_id: promptId, source, index: "0007", media_count: 4 }], total: 1, limit: 20000, offset: 0, max_media_count: 4 };
    else if (url.pathname.endsWith("/prompt-registry/lookup")) body = {
      prompt_id: promptId, source, index: "0007",
      entry: { source, index: "0007", prompt: "A quiet mountain lake at dawn, distant peaks and soft reflections in pale green and gold. Natural light, detailed landscape, balanced composition.", negative_prompt: null },
      media: mediaRows, total_media: 4, limit: 48, offset: 0,
    };
    else if (url.pathname.endsWith("/usage/navigation")) body = navigation(url.searchParams.get("media_id"));
    else if (/\/media\/[^/]+\/navigation$/.test(url.pathname)) body = navigation(url.pathname.split("/")[4]);
    else if (/\/media\/[^/]+\/workflow$/.test(url.pathname)) body = {
      display_fields: { prompt_id: { value: promptId }, character_lora: { value: character }, lora_list: { value: [] } }, status: "parsed",
    };
    else if (/\/media\/[^/]+$/.test(url.pathname)) body = mediaRows.find((media) => media.id === url.pathname.split("/")[4]) ?? {};
    else if (url.pathname === "/api/v1/media") body = { items: mediaRows, total: 4, limit: 48, offset: 0 };
    await route.fulfill({ json: body });
  });
  await context.route("**/qa-media/**", (route) => route.fulfill({
    contentType: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1536"><path fill="#9ab9ba" d="M0 0h1024v1536H0z"/><path fill="#566961" d="M0 750 250 300 500 790 750 450 1024 840v696H0z"/><path fill="#758c7a" d="M0 950 380 660 720 1050 1024 780v756H0z"/><path fill="#b2bba4" d="M0 1180h1024v356H0z"/></svg>',
  }));
}

async function registryGeometry(page) {
  return page.evaluate(() => {
    const rect = (element) => {
      const r = element.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
    };
    const labels = [...document.querySelectorAll(".prompt-registry-heatmap-filters > label")];
    const booleans = [...document.querySelectorAll(".prompt-registry-heatmap-scope label")];
    const canvas = document.querySelector(".prompt-registry-heatmap-canvas");
    return {
      sidebar: rect(document.querySelector(".prompt-registry-sidebar")),
      usage: rect(document.querySelector(".prompt-registry-usage-column")),
      heatmap: rect(document.querySelector(".prompt-registry-heatmap-panel")),
      controls: labels.map(rect), inputs: labels.map((element) => rect(element.querySelector("select,input"))),
      booleans: booleans.map((element) => ({ label: rect(element), input: rect(element.querySelector("input")), direction: getComputedStyle(element).flexDirection })),
      pageWidth: document.documentElement.scrollWidth, viewport: innerWidth,
      canvas: { width: canvas.width, height: canvas.height, cssWidth: canvas.getBoundingClientRect().width, cssHeight: canvas.getBoundingClientRect().height, dpr: devicePixelRatio },
    };
  });
}

function registryErrors(geometry) {
  const errors = [];
  const intersect = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
  if (intersect(geometry.sidebar, geometry.usage)) errors.push("sidebar and usage overlap");
  if (intersect(geometry.heatmap, geometry.usage)) errors.push("heatmap panel overlaps usage");
  if (geometry.heatmap.right > geometry.sidebar.right + 1) errors.push("heatmap panel escapes sidebar");
  if (geometry.pageWidth > geometry.viewport + 1) errors.push("document horizontal overflow");
  geometry.controls.forEach((a, index) => {
    if (a.left < geometry.heatmap.left || a.right > geometry.heatmap.right + 1) errors.push(`filter ${index} escapes heatmap panel`);
    for (let other = index + 1; other < geometry.controls.length; other++) if (intersect(a, geometry.controls[other])) errors.push(`filters ${index}/${other} overlap`);
    const input = geometry.inputs[index];
    if (input.left < a.left - 1 || input.right > a.right + 1) errors.push(`filter input ${index} escapes label`);
  });
  geometry.booleans.forEach((boolean, index) => {
    if (boolean.input.width > 24 || boolean.input.height > 24) errors.push(`boolean ${index} oversized`);
    if (boolean.direction !== "row") errors.push(`boolean ${index} is not inline with label`);
  });
  const canvas = geometry.canvas;
  if (Math.abs(canvas.width / canvas.dpr - canvas.cssWidth) > 1 || Math.abs(canvas.height / canvas.dpr - canvas.cssHeight) > 1) errors.push("heatmap bitmap is stretched relative to its CSS/DPR dimensions");
  return errors;
}

async function runRegistryChecks(browser) {
  const failures = [];
  for (const width of [1280, 1440, 1728, 1920, 3840, 390]) {
    for (const collapsed of [false, true]) {
      const context = await browser.newContext({ viewport: { width, height: 1100 }, deviceScaleFactor: width === 3840 ? 1 : 2 });
      try {
        await context.addInitScript((collapsed) => localStorage.setItem("comfy-gallery.sidebar-collapsed", String(collapsed)), collapsed);
        await installFixtureRoutes(context);
        const page = await context.newPage();
        await page.goto(`${baseUrl}/registries/prompts?prompt_id=${encodeURIComponent(promptId)}`);
        await page.getByRole("heading", { name: "Media using this prompt" }).waitFor();
        await page.getByLabel("Heatmap source", { exact: true }).selectOption(source);
        await page.getByLabel("Heatmap character LoRA", { exact: true }).selectOption(character);
        // ResizeObserver and the canvas drawing effect settle on successive frames.
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const geometry = await registryGeometry(page);
        const errors = registryErrors(geometry);
        console.log(JSON.stringify({ surface: "registry", width, collapsed, errors, sidebarWidth: geometry.sidebar.width, panelWidth: geometry.heatmap.width }));
        if (errors.length) failures.push({ width, collapsed, errors });
        if (process.env.CG_BROWSER_QA_SCREENSHOTS) {
          await fs.mkdir(process.env.CG_BROWSER_QA_SCREENSHOTS, { recursive: true });
          await page.screenshot({ path: path.join(process.env.CG_BROWSER_QA_SCREENSHOTS, `registry-${width}-${collapsed}.png`) });
        }
      } finally { await context.close(); }
    }
  }
  assert.equal(failures.length, 0, JSON.stringify(failures));
}

module.exports = { baseUrl, promptId, source, character, mediaRows, loadPlaywright, installFixtureRoutes, registryGeometry, registryErrors, runRegistryChecks };

if (require.main === module) {
  (async () => {
    const browser = await loadPlaywright().chromium.launch({ channel: process.env.CG_BROWSER_QA_CHANNEL || "chrome", headless: true });
    try { await runRegistryChecks(browser); }
    finally { await browser.close(); }
  })().catch((error) => { console.error(error); process.exitCode = 1; });
}
