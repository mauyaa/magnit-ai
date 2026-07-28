import { mkdirSync } from "node:fs";

import { chromium } from "playwright";

const OUT = process.argv[2];
const ROUTES = process.argv.slice(3);
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});

for (const route of ROUTES) {
  const name = route === "/" ? "home" : route.replace(/^\//, "").replace(/\//g, "-");
  await page.goto(`http://localhost:5173${route}`, { waitUntil: "networkidle" }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`${name.padEnd(16)} ${page.url()}`);
}

await browser.close();
