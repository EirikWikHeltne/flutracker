// Renders the dashboard's Karo line icons (the <symbol>s in docs/index.html) to PNG for the e-mail.
// Outlook cannot show SVG, so the e-mail uses these PNGs (3x, shown at 16 px).
// Run from the repository root: node tools/render_email_icons.js
const fs = require("fs");
const { chromium } = require("playwright");

const NAMES = ["virus", "calendar", "pulse", "bulb", "layers", "globe", "gauge", "book"];
const COLORS = { navy: "#110B36", peach: "#FAD7C2" };
const PX = 48;

(async () => {
  const src = fs.readFileSync("docs/index.html", "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: PX, height: PX } });
  for (const name of NAMES) {
    const m = src.match(new RegExp(`<symbol id="i-${name}" viewBox="([^"]+)"([^>]*)>([\\s\\S]*?)</symbol>`));
    if (!m) throw new Error(`icon ${name} not found`);
    for (const [cname, hex] of Object.entries(COLORS)) {
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${PX}" height="${PX}" viewBox="${m[1]}"${m[2].replace(/currentColor/g, hex)}>${m[3]}</svg>`;
      await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
      await page.locator("svg").screenshot({ path: `docs/data/icons/${name}-${cname}.png`, omitBackground: true });
    }
  }
  await browser.close();
})();
