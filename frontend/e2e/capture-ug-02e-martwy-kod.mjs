/** Story 5.10 follow-up — zrzut ekranu „Błędy kodu" z kategorią „Martwy kod" (§4.6).
 *  Login anna.demo → projekt demo → ew. klik „Skanuj kod" (domyślne kategorie
 *  z dead_code) → poll GET /code-errors aż dead_code > 0 → zrzut viewport 1440×900. */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false }); console.log(`📸 ${n}`); };

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
page.setDefaultTimeout(30000);

const api = async (path) => page.evaluate(async (p) => (await (await fetch(`/api/v1${p}`, { credentials: "include" })).json()), path);

// --- login ---
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill("anna.demo@testgen.nexio.pl");
await page.locator('input[type="password"]').first().fill("Qa-Demo-2026!Podrecznik");
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
console.log("✅ login");

// --- projekt demo ---
const projects = await api("/projects");
const pid = projects.projects.find((p) => p.name.includes("Sklep internetowy"))?.id ?? projects.projects[0].id;
console.log("projekt:", pid);

// --- stan code-errors ---
let list = await api(`/projects/${pid}/code-errors?size=100`);
console.log("code-errors total:", list.total, "| by_category:", JSON.stringify(list.summary?.by_category));

if (!(list.summary?.by_category?.dead_code > 0)) {
  // uruchom skan przyciskiem (Angular obsłuży CSRF)
  await page.goto(`${BASE}/projects/${pid}/code-errors`, { waitUntil: "networkidle" });
  const btn = page.getByRole("button", { name: /Skanuj kod/i });
  console.log("przycisk Skanuj kod:", await btn.count());
  if (await btn.count()) {
    await btn.first().click();
    // poll aż dead_code się pojawi (skan asynchroniczny)
    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(4000);
      list = await api(`/projects/${pid}/code-errors?size=100`);
      console.log(`poll ${i + 1}: total=${list.total} dead_code=${list.summary?.by_category?.dead_code ?? 0}`);
      if ((list.summary?.by_category?.dead_code ?? 0) > 0) break;
    }
  }
}

// --- ekran + zrzut ---
await page.goto(`${BASE}/projects/${pid}/code-errors`, { waitUntil: "networkidle" });
await page.waitForTimeout(4000);
let rows = 0;
for (let i = 0; i < 6; i++) {
  rows = await page.locator("table tbody tr, mat-row").count().catch(() => 0);
  if (rows > 0) break;
  console.log(`czekam na tabelę (próba ${i + 1})...`);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(4000);
}
const chips = await page.locator(".cat-dead_code").count().catch(() => 0);
console.log("wierszy tabeli:", rows, "| chipów Martwy kod:", chips);
await shot(page, "ug-02-16b-martwy-kod");

await browser.close();
console.log("✅ capture 5.10 zakończony");
