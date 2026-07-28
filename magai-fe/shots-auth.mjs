import { mkdirSync, readFileSync } from "node:fs";

import { chromium } from "playwright";

const [OUT, TOKEN_DIR, ...ROUTES] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });

const access = readFileSync(`${TOKEN_DIR}/token.txt`, "utf8").trim();
const refresh = readFileSync(`${TOKEN_DIR}/refresh.txt`, "utf8").trim();

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});

// The app keeps tokens in sessionStorage; seed them before the app boots so the
// first render is already authenticated.
await page.goto("http://localhost:5173/");
await page.evaluate(
  ([a, r]) => {
    sessionStorage.setItem("magnitai.access_token", a);
    sessionStorage.setItem("magnitai.refresh_token", r);
  },
  [access, refresh],
);

for (const route of ROUTES) {
  const name = route === "/" ? "home" : route.replace(/^\//, "").replace(/\//g, "-");
  await page.goto(`http://localhost:5173${route}`, { waitUntil: "networkidle" }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1600);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`${name.padEnd(20)} ${page.url()}`);
}

await browser.close();
