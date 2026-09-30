/** Story 9.2 — etap 2: upload plików demo + uruchomienie analizy (UI). */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const DEMO = join(tmpdir(), "ug-demo");
const shot = async (p, n, o = {}) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false, ...o }); console.log("📸 " + n); };

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);

const projects = await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()));
const pid = projects.projects?.[0]?.id;
console.log("PROJECT_ID:", pid);

// --- pliki projektu ---
await page.goto(`${BASE}/projects/${pid}/files`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot(page, "ug-01-07-zakladka-pliki");
const fileInput = page.locator('input[type="file"]').first();
console.log("file inputs:", await page.locator('input[type="file"]').count());
await fileInput.setInputFiles([join(DEMO, "app.py"), join(DEMO, "services.py"), join(DEMO, "db.py"), join(DEMO, "utils.py")]);
await page.waitForTimeout(2500); // upload + progress
await shot(page, "ug-01-08-upload-zakonczony");
await page.waitForTimeout(2000);
await shot(page, "ug-01-09-lista-plikow", { fullPage: true });
const filesList = await page.evaluate(async () => (await (await fetch(`/api/v1/projects/${location.pathname.split("/")[2]}/files`, { credentials: "include" })).json()).catch(e => String(e)));
console.log("FILES:", JSON.stringify(filesList).slice(0, 300));

await browser.close();
