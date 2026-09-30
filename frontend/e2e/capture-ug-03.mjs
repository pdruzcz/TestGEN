/**
 * Story 9.4 — zrzuty do podręcznika cz. 3 (rozdziały 9-13) z żywego UI.
 * Wymaga: plan demo = premium (utrzymany z 9.3), projekt „Sklep internetowy (demo)"
 * z danymi z 9.3. Dokłada próbki podatne z golden data + package.json (API, .json
 * odrzucane przez FE), uruchamia skany/luki/rekomendacje/snapshoty/raport.
 * Uruchomienie (frontend/): node e2e/capture-ug-03.mjs
 */
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const GOLDEN = resolve("..", "backend", "tests", "golden_data");

const VULN = [
  join(GOLDEN, "security", "vulnerable_code", "sqli", "sqli_python.py"),
  join(GOLDEN, "security", "vulnerable_code", "xss", "xss_reflected_python.py"),
  join(GOLDEN, "security", "vulnerable_code", "secrets", "secrets_password_python.py"),
];
const PKG = readFileSync(join(GOLDEN, "security", "dependency", "package.json"));

const shot = async (p, n, o = {}) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false, ...o }); console.log(`📸 ${n}`); };
const step = async (l, fn) => { try { await fn(); } catch (e) { console.log(`⚠️  ${l}: ${String(e).split("\n")[0].slice(0, 150)}`); } };
const api = (page) => async (path, init = {}) =>
  page.evaluate(async ({ path, init }) => {
    const xsrf = document.cookie.split("; ").find((c) => c.startsWith("XSRF-TOKEN="))?.slice(11) ?? "";
    const r = await fetch(`/api/v1${path}`, { credentials: "include", ...init, headers: { "X-XSRF-TOKEN": xsrf, ...(init.headers ?? {}) } });
    return { status: r.status, body: (await r.text()).slice(0, 500) };
  }, { path, init });

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
page.setDefaultTimeout(25000);
const A = api(page);

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
const projects = await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()));
const pid = projects.projects.find((p) => p.name.includes("Sklep internetowy"))?.id ?? projects.projects[0].id;
const card = `${BASE}/projects/${pid}`;
console.log("PID:", pid);

// ====== PRZYGOTOWANIE DANYCH ======
await step("upload próbek podatnych (UI)", async () => {
  await page.goto(`${card}/files`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.locator('input[type="file"]').first().setInputFiles(VULN);
  await page.waitForTimeout(4000);
});
await step("upload package.json (API)", async () => {
  const bytes = Array.from(PKG);
  const r = await page.evaluate(async ({ pid, bytes }) => {
    const xsrf = document.cookie.split("; ").find((c) => c.startsWith("XSRF-TOKEN="))?.slice(11) ?? "";
    const fd = new FormData();
    fd.append("files", new File([new Uint8Array(bytes)], "package.json", { type: "application/json" }));
    const resp = await fetch(`/api/v1/projects/${pid}/upload`, { method: "POST", credentials: "include", headers: { "X-XSRF-TOKEN": xsrf }, body: fd });
    return { status: resp.status, body: (await resp.text()).slice(0, 300) };
  }, { pid, bytes });
  console.log("  package.json:", JSON.stringify(r));
});

// ====== ROZDZIAŁ 11: bezpieczeństwo ======
const runScan = async (optionText, label) => {
  await page.goto(`${card}/security`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.locator("mat-select").first().click();
  await page.locator(`mat-option:has-text('${optionText}')`).first().click();
  await page.getByRole("button", { name: /Uruchom skan/ }).first().click();
  console.log(`  skan ${label} uruchomiony`);
  for (let i = 0; i < 50; i++) {
    await page.waitForTimeout(4000);
    const r = await A(`/projects/${pid}/security-scans`);
    const scans = JSON.parse(r.body ?? "[]");
    const mine = Array.isArray(scans) ? scans.filter((s) => s.scan_type === label) : (scans.scans ?? []);
    const done = mine.length && mine.every((s) => ["completed", "failed"].includes(s.status));
    if (done) { console.log(`  skan ${label}: ${mine.map((s) => s.status).join(",")}`); return mine; }
  }
  console.log(`  skan ${label}: timeout`);
  return null;
};

await step("R11: formularz skanu (zrzut 07)", async () => {
  await page.goto(`${card}/security`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot(page, "ug-03-07-uruchamianie-skanu");
});
await step("R11: SAST", () => runScan("Skanowanie statyczne", "sast"));
await step("R11: TAINT", () => runScan("Taint analysis", "taint"));
await step("R11: DEPENDENCY", () => runScan("Zależności", "dependency"));

await step("R11: podatności (zrzut 08)", async () => {
  await page.goto(`${card}/security`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "ug-03-08-podatnosci", { fullPage: true });
});
await step("R11: zależności + SBOM (zrzut 09)", async () => {
  await page.goto(`${card}/security`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const sec = page.locator("text=Podatne zależności").first();
  if (await sec.count()) await sec.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(800);
  await shot(page, "ug-03-09-zaleznosci-sbom");
});
await step("R11: rekomendacja podatności (zrzut 10)", async () => {
  await page.goto(`${card}/security`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: /Pokaż rekomendację/ }).first().click();
  await page.waitForTimeout(1500);
  const gen = page.getByRole("button", { name: /Generuj rekomendację/ }).first();
  if (await gen.count()) { await gen.click(); await page.waitForTimeout(6000); }
  const det = page.locator("text=Opis problemu").first();
  if (await det.count()) await det.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(600);
  await shot(page, "ug-03-10-rekomendacja-podatnosci");
});
await step("R11: dashboard ryzyka (zrzut 11)", async () => {
  await page.goto(`${card}/security`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: /Oblicz priorytetyzację/ }).first().click().catch(() => {});
  await page.waitForTimeout(4000);
  const dash = page.locator("text=Dashboard ryzyka").first();
  if (await dash.count()) await dash.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(800);
  await shot(page, "ug-03-11-dashboard-ryzyka");
});

// ====== ROZDZIAŁ 12: luki ======
await step("R12: analiza luk + tabela (zrzut 12)", async () => {
  await page.goto(`${card}/gap-analysis`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: /Uruchom analizę/ }).first().click();
  await page.waitForTimeout(1200);
  // dialog wyboru dokumentów — zaznacz wszystko i potwierdź
  const dlg = page.locator("mat-dialog-container, .cdk-overlay-pane").first();
  if (await dlg.count()) {
    const cbs = dlg.locator("mat-checkbox, input[type=checkbox]");
    const n = await cbs.count();
    for (let i = 0; i < n; i++) await cbs.nth(i).click().catch(() => {});
    await dlg.getByRole("button", { name: /Potwierdź|Zatwierdź|Uruchom|OK/ }).first().click().catch(() => page.keyboard.press("Enter"));
  }
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(4000);
    const ok = await page.locator("text=/Brakujące|Nadmiarowe|success/").count().catch(() => 0);
    if (ok) break;
  }
  await page.goto(`${card}/gap-analysis`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot(page, "ug-03-12-luki-funkcjonalne", { fullPage: true });
});
await step("R12: rekomendacje (zrzut 13)", async () => {
  await page.goto(`${card}/recommendations`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: /Generuj rekomendacje/ }).first().click().catch(() => {});
  await page.waitForTimeout(8000);
  await page.goto(`${card}/recommendations`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot(page, "ug-03-13-rekomendacje", { fullPage: true });
});
await step("R12: snapshoty + porównanie (zrzut 14)", async () => {
  await page.goto(`${card}/comparison`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  for (const label of ["Przed poprawkami", "Po poprawkach"]) {
    await page.getByRole("button", { name: /Utwórz snapshot/ }).first().click().catch(() => {});
    await page.waitForTimeout(1000);
    const dlg = page.locator("mat-dialog-container, .cdk-overlay-pane").first();
    if (await dlg.count()) {
      const inp = dlg.locator("input:visible").first();
      if (await inp.count()) await inp.fill(label);
      await dlg.getByRole("button", { name: /Zapisz|Utwórz|OK|Potwierdź/ }).first().click().catch(() => page.keyboard.press("Enter"));
    }
    await page.waitForTimeout(3000);
  }
  await page.goto(`${card}/comparison`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.locator("mat-select").nth(0).click().catch(() => {});
  await page.locator("mat-option").nth(0).click().catch(() => {});
  await page.locator("mat-select").nth(1).click().catch(() => {});
  await page.locator("mat-option").nth(1).click().catch(() => {});
  await page.getByRole("button", { name: /Porównaj/ }).first().click().catch(() => {});
  await page.waitForTimeout(3000);
  await shot(page, "ug-03-14-porownanie-wersji", { fullPage: true });
});

// ====== ROZDZIAŁ 9: przypadki testowe ======
await step("R9: lista TC + grupowanie (zrzut 01)", async () => {
  await page.goto(`${card}/test-cases`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const grp = page.locator("mat-select:has-text('Grupuj'), mat-select").filter({ hasText: /Grupuj|Brak grupowania/ }).first();
  if (await grp.count()) {
    await grp.click();
    await page.locator("mat-option:has-text('Priorytet')").first().click().catch(() => {});
    await page.waitForTimeout(1200);
  }
  await shot(page, "ug-03-01-lista-przypadkow");
});
await step("R9: operacje masowe (zrzut 04)", async () => {
  const cbs = page.locator("table input[type=checkbox], mat-checkbox input");
  const n = Math.min(2, await cbs.count());
  for (let i = 0; i < n; i++) await cbs.nth(i + 1).click().catch(() => cbs.nth(i).click()); // pomijaj select-all
  await page.waitForTimeout(800);
  await shot(page, "ug-03-04-operacje-masowe");
});
await step("R9: eksport TMS (zrzut 16)", async () => {
  await page.getByRole("button", { name: /^Eksportuj/ }).first().click();
  await page.waitForTimeout(1200);
  await shot(page, "ug-03-16-eksport-tms");
  await page.getByRole("button", { name: /Anuluj/ }).first().click().catch(() => page.keyboard.press("Escape"));
  await page.waitForTimeout(500);
});
await step("R9: edytor TC (zrzut 02)", async () => {
  const edit = page.locator("button:has(mat-icon:text('edit'))").first();
  const editBtn = page.getByRole("button", { name: /Edytuj/ }).first();
  if (await edit.count()) await edit.click();
  else if (await editBtn.count()) await editBtn.click();
  await page.waitForTimeout(1500);
  const form = page.locator("text=Kroki testowe").first();
  if (await form.count()) { await form.scrollIntoViewIfNeeded().catch(() => {}); await page.waitForTimeout(500); await shot(page, "ug-03-02-edytor-przypadku"); }
  else { console.log("  (edytor niedostępny — zrzut 02 pominięty)"); }
  await page.getByRole("button", { name: /Anuluj/ }).first().click().catch(() => page.keyboard.press("Escape"));
});
await step("R9: szczegóły TC (zrzut 03)", async () => {
  await page.goto(`${card}/test-cases`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.locator("table tbody a, table tbody tr td a, a:has-text('test')").first().click().catch(async () => {
    await page.locator("table tbody tr").first().click();
  });
  await page.waitForTimeout(2000);
  await shot(page, "ug-03-03-szczegoly-przypadku", { fullPage: true });
});

// ====== ROZDZIAŁ 10: kod testowy ======
await step("R10: generator Gherkin (zrzut 06)", async () => {
  await page.goto(`${card}/gherkin`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const gen = page.getByRole("button", { name: /Generuj scenariusze/ }).first();
  const flows = page.locator("mat-checkbox, input[type=checkbox]");
  const nf = await flows.count();
  if (gen && (await gen.count()) && nf) {
    for (let i = 0; i < Math.min(2, nf); i++) await flows.nth(i).click().catch(() => {});
    await gen.click();
    await page.waitForTimeout(8000);
    await page.goto(`${card}/gherkin`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
  }
  await shot(page, "ug-03-06-generator-gherkin", { fullPage: true });
});
await step("R10: generator Cypress (zrzut 05)", async () => {
  await page.goto(`${card}/codegen/cypress`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const cbs = page.locator("mat-checkbox, input[type=checkbox]");
  const n = await cbs.count();
  for (let i = 0; i < Math.min(2, n); i++) await cbs.nth(i).click().catch(() => {});
  await page.waitForTimeout(500);
  await shot(page, "ug-03-05-generator-cypress");
  await page.getByRole("button", { name: /Generuj kod Cypress/ }).first().click().catch(() => {});
  await page.waitForTimeout(10000);
  const res = page.locator("text=Pobierz").last();
  if (await res.count()) { await res.scrollIntoViewIfNeeded().catch(() => {}); await page.waitForTimeout(500); }
  await shot(page, "ug-03-05b-generator-cypress-wynik");
});

// ====== ROZDZIAŁ 13: raporty ======
await step("R13: generator raportów (zrzut 15)", async () => {
  await page.goto(`${card}/reports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.locator("mat-radio-button:has-text('Podsumowanie wykonawcze')").first().click().catch(() => {});
  await page.getByRole("button", { name: /Generuj raport/ }).first().click();
  await page.waitForTimeout(3000);
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(3000);
    const done = await page.locator("text=/Raport — |Wygenerowano/").count().catch(() => 0);
    if (done) break;
  }
  await page.waitForTimeout(1500);
  await shot(page, "ug-03-15-generator-raportow", { fullPage: true });
});

await browser.close();
console.log("✅ capture-ug-03 zakończony");
