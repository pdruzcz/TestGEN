import { chromium } from "@playwright/test";
const BASE = "https://testgen.nexio.pl";
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "pl-PL" })).newPage();
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill("anna.demo@testgen.nexio.pl");
await page.locator('input[type="password"]').first().fill("Qa-Demo-2026!Podrecznik");
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/, { timeout: 20000 });
await page.waitForTimeout(1500);
const me = await page.evaluate(async () => {
  const r = await fetch("/api/v1/users/me", { credentials: "include" });
  return { status: r.status, body: await r.json() };
}).catch((e) => ({ error: String(e) }));
console.log("ME:", JSON.stringify(me).slice(0, 500));
const projects = await page.evaluate(async () => {
  const r = await fetch("/api/v1/projects?page=1&size=5", { credentials: "include" });
  return { status: r.status, body: await r.json() };
}).catch((e) => ({ error: String(e) }));
console.log("PROJECTS:", JSON.stringify(projects).slice(0, 800));
await browser.close();
