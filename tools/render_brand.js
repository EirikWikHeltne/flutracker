// Renders the flu tracker's logo (docs/img/brand/logo.svg) to favicon PNGs and builds the
// 1200x630 link-preview thumbnail (og-image.png) shown when the dashboard link is shared.
// Run from the repository root: node tools/render_brand.js
const fs = require("fs");
const { chromium } = require("playwright");

const OUT = "docs/img/brand";
const logo = fs.readFileSync(`${OUT}/logo.svg`, "utf8");

const ogHtml = `<!doctype html><html><head><style>
  html,body{margin:0}
  .card{width:1200px;height:630px;position:relative;overflow:hidden;background:#110B36;color:#fff;
        font-family:Georgia,"Times New Roman",serif;box-sizing:border-box;padding:84px 88px}
  .wave{position:absolute;inset:auto 0 0 0;width:1200px;height:150px}
  .logo{width:132px;height:132px;display:block}
  .logo svg{width:100%;height:100%}
  .eyebrow{margin:44px 0 10px;font-size:24px;letter-spacing:.14em;text-transform:uppercase;color:#9DE3C2}
  h1{margin:0;font-size:82px;font-weight:normal;line-height:1.05;color:#FAD7C2}
  .sub{margin:22px 0 0;font-size:30px;color:#d9d6e6;max-width:820px;line-height:1.35}
  .countries{position:absolute;right:88px;top:96px;display:flex;flex-direction:column;gap:16px;font-size:24px;color:#ece9f5}
  .countries span{display:flex;align-items:center;gap:14px}
  .countries i{width:16px;height:16px;border-radius:50%;display:inline-block}
</style></head><body><div class="card">
  <svg class="wave" viewBox="0 0 1200 300" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 290 C 180 288, 300 280, 420 250 S 600 60, 700 70 S 860 250, 1000 278 S 1150 290, 1200 290 L1200 300 L0 300Z" fill="#FAD7C2" opacity=".10"/>
    <path d="M0 290 C 180 288, 300 280, 420 250 S 600 60, 700 70 S 860 250, 1000 278 S 1150 290, 1200 290" fill="none" stroke="#FAD7C2" stroke-width="4" opacity=".55"/>
    <path d="M0 292 C 200 290, 330 285, 460 270 S 640 170, 740 175 S 900 270, 1040 284 S 1160 292, 1200 292" fill="none" stroke="#9F9DB1" stroke-width="3" stroke-dasharray="10 10" opacity=".5"/>
  </svg>
  <div class="logo">${logo}</div>
  <p class="eyebrow">Weekly surveillance</p>
  <h1>Nordic Flu Tracker</h1>
  <p class="sub">Influenza, COVID-19 and RSV compared with previous seasons</p>
  <div class="countries">
    <span><i style="background:#7E73E0"></i>Norway</span>
    <span><i style="background:#D96A42"></i>Sweden</span>
    <span><i style="background:#1F9E8F"></i>Denmark</span>
    <span><i style="background:#E062A6"></i>Finland</span>
  </div>
</div></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (const [name, px] of [["favicon-32.png", 32], ["favicon-192.png", 192], ["apple-touch-icon.png", 180], ["logo-512.png", 512]]) {
    await page.setViewportSize({ width: px, height: px });
    await page.setContent(`<html><body style="margin:0;background:transparent">${logo.replace("<svg ", `<svg width="${px}" height="${px}" `)}</body></html>`);
    await page.locator("svg").screenshot({ path: `${OUT}/${name}`, omitBackground: true });
  }
  await page.setViewportSize({ width: 1200, height: 630 });
  await page.setContent(ogHtml);
  await page.locator(".card").screenshot({ path: `${OUT}/og-image.png` });
  await browser.close();
})();
