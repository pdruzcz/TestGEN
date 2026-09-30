/**
 * Story 9.3 — zrzuty do podręcznika cz. 2 (rozdziały 4-8) z żywego UI.
 * Wymaga: plan demo = premium (admin: PUT /tenants/{id}/plan), projekt
 * „Sklep internetowy (demo)" z plikami kodu z 9.2.
 * Dane demo (dokumenty/UML/GUI) wgrywane w locie z backend/tests/golden_data.
 * Uruchomienie (frontend/): node e2e/capture-ug-02.mjs
 */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const GOLDEN = resolve("..", "backend", "tests", "golden_data");

// materiały demo (golden data, PL)
const DOCS = [
  join(GOLDEN, "docs", "frd", "frd_modul_uzytkownikow.pdf"),
  join(GOLDEN, "docs", "manual", "podrecznik_operatora.md"),
  join(GOLDEN, "docs", "brd", "brd_platnosci.docx"),
];
const UMLS = [
  join(GOLDEN, "uml", "class", "class_hierarchy.puml"),
  join(GOLDEN, "uml", "sequence", "sequence_loop.puml"),
  join(GOLDEN, "uml", "use_case", "usecase_checkout.puml"),
  join(GOLDEN, "uml", "activity", "activity_simple.puml"),
];
const GUIS = [
  join(GOLDEN, "gui", "forms", "login_form.png"),
  join(GOLDEN, "gui", "forms", "contact_form.png"),
  join(GOLDEN, "gui", "dashboards", "project_overview.png"),
];

const shot = async (page, name, opts = {}) => {
  await page.screenshot({ path: join(IMG_DIR, `${name}.png`), fullPage: false, ...opts });
  console.log(`📸 ${name}`);
};
const step = async (label, fn) => {
  try {
    await fn();
  } catch (e) {
    console.log(`⚠️  ${label}: ${String(e).split("\n")[0].slice(0, 140)}`);
  }
};
const textBtn = (page, re) => page.getByRole("button", { name: re }).first();
const linkBtn = (page, re) => page.locator(`a:has-text('${re}')`).first();

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
page.setDefaultTimeout(20000);

// --- logowanie ---
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
console.log("✅ zalogowano");

const feats = await page.evaluate(async () => (await (await fetch("/api/v1/billing/features", { credentials: "include" })).json()));
console.log("PLAN:", feats.current_plan, "| uml locked:", feats.modules?.find((m) => m.key === "uml")?.locked);
if (feats.modules?.find((m) => m.key === "uml")?.locked) {
  console.log("❌ Moduły nadal zablokowane — najpierw podbij plan do premium (admin). Przerywam.");
  await browser.close();
  process.exit(1);
}

const projects = await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()));
const pid = projects.projects.find((p) => p.name.includes("Sklep internetowy"))?.id ?? projects.projects[0].id;
console.log("PID:", pid);
const card = `${BASE}/projects/${pid}`;

// ============ ROZDZIAŁ 4 ============
await step("R4: lista projektów", async () => {
  await page.goto(`${BASE}/projects`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-02-lista-projektow");
});
await step("R4: dialog nowy projekt (anulowany)", async () => {
  await textBtn(page, /Nowy projekt/).click();
  await page.waitForTimeout(800);
  const dlg = page.locator("mat-dialog-container, .cdk-overlay-pane").first();
  await dlg.locator("input:visible").first().fill("Aplikacja mobilna (przykład)");
  await shot(page, "ug-02-01-nowy-projekt");
  await dlg.getByRole("button", { name: /Anuluj/ }).first().click();
  await page.waitForTimeout(400);
});
await step("R4: dialog usuwania (anulowany)", async () => {
  await page.waitForTimeout(800);
  const row = page.locator("table tbody tr, mat-row").filter({ hasText: "Sklep internetowy" }).first();
  await row.locator('button:has(mat-icon:text("delete")), button[aria-label*="Usuń"]').first().click();
  await page.waitForTimeout(800);
  await shot(page, "ug-02-03-usuwanie-projektu");
  await page.getByRole("button", { name: /^Anuluj$/ }).first().click().catch(() => page.keyboard.press("Escape"));
});
await step("R4: karta projektu", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-04-karta-projektu", { fullPage: true });
});
await step("R4: użytkownicy firmy", async () => {
  await page.goto(`${BASE}/settings/users`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-05-uzytkownicy");
});

// ============ ROZDZIAŁ 5 ============
await step("R5: wgraj pliki + lista plików", async () => {
  await page.goto(`${card}/files`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-06-wgraj-pliki");
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-07-lista-plikow", { fullPage: true });
});
await step("R5: zakładka repozytorium", async () => {
  await page.locator("[role=tab]:has-text('Połącz repozytorium'), a:has-text('Połącz repozytorium')").first().click();
  await page.waitForTimeout(900);
  await shot(page, "ug-02-11-repozytorium");
});
await step("R5: upload dokumentacji", async () => {
  await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const input = page.locator('input[type="file"][accept*="pdf"], input[type="file"]').first();
  await input.setInputFiles(DOCS);
  // czekaj aż wszystkie dokumenty osiągną status Gotowy/Błąd (parsowanie async)
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(3000);
    const docs = await page.evaluate(async (pid) => (await (await fetch(`/api/v1/projects/${pid}/documents`, { credentials: "include" })).json()).catch(() => null), pid);
    const list = Array.isArray(docs) ? docs : (docs?.documents ?? docs?.items ?? []);
    const busy = list.filter((d) => !["ready", "failed"].includes(d.status)).length;
    console.log(`  dokumenty: ${list.length}, w przetwarzaniu: ${busy}`);
    if (list.length >= DOCS.length && busy === 0) break;
  }
  await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-08-dokumenty", { fullPage: true });
});
await step("R5: upload UML", async () => {
  await page.goto(`${card}/uml`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator('input[type="file"]').first().setInputFiles(UMLS);
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(3000);
    const d = await page.evaluate(async (pid) => (await (await fetch(`/api/v1/projects/${pid}/uml`, { credentials: "include" })).json()).catch(() => null), pid);
    const list = d?.diagrams ?? [];
    const busy = list.filter((x) => !["parsed", "failed", "error"].includes(x.status)).length;
    console.log(`  uml: ${list.length}, w przetwarzaniu: ${busy}`);
    if (list.length >= UMLS.length && busy === 0) break;
  }
  await page.goto(`${card}/uml`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-09-diagramy-uml", { fullPage: true });
});
await step("R5: upload GUI", async () => {
  await page.goto(`${card}/gui`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator('input[type="file"]').first().setInputFiles(GUIS);
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(3000);
    const g = await page.evaluate(async (pid) => (await (await fetch(`/api/v1/projects/${pid}/gui`, { credentials: "include" })).json()).catch(() => null), pid);
    const list = g?.screenshots ?? [];
    const busy = list.filter((x) => !["completed", "analysed", "analyzed", "failed", "error"].includes(x.status)).length;
    console.log(`  gui: ${list.length}, w przetwarzaniu: ${busy}`);
    if (list.length >= GUIS.length && busy === 0) break;
  }
  await page.goto(`${card}/gui`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "ug-02-10-zrzuty-gui", { fullPage: true });
});

// ============ ROZDZIAŁ 7 (najpierw analiza dokumentacji) ============
await step("R7: analiza dokumentacji", async () => {
  await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await textBtn(page, /Analizuj dokumentacj/).click();
  await page.waitForTimeout(4000);
});
await step("R7: wymagania", async () => {
  for (let i = 0; i < 30; i++) {
    await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
    const req = await linkBtn(page, "Wymagania").count();
    if (req) break;
    await page.waitForTimeout(4000);
  }
  await linkBtn(page, "Wymagania").first().click();
  await page.waitForTimeout(2500);
  // wybierz dokument z największą liczbą wymagań (FRD)
  const frd = page.locator("a:has-text('frd'), a:has-text('FRD')").first();
  if (await frd.count()) await frd.click().catch(() => {});
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-18-wymagania", { fullPage: true });
});
await step("R7: niespójności", async () => {
  await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.locator("a:has-text('Niespójności'), button:has-text('Niespójności')").first().click();
  await page.waitForTimeout(2000);
  await shot(page, "ug-02-19-niespojnosci", { fullPage: true });
});
await step("R7: glosariusz", async () => {
  await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.locator("a:has-text('Glosariusz'), button:has-text('Glosariusz')").first().click();
  await page.waitForTimeout(2000);
  await shot(page, "ug-02-20-glosariusz", { fullPage: true });
});

// ============ ROZDZIAŁ 6 (analiza główna) ============
await step("R6: parametry analizy + uruchomienie", async () => {
  await page.goto(`${card}/analysis`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  // zaznacz moduły UML/GUI (kod+TC już domyślnie)
  for (const label of ["Analiza UML", "Analiza GUI"]) {
    const cb = page.locator(`mat-checkbox:has-text('${label}'), label:has-text('${label}')`).first();
    if (await cb.count()) await cb.click().catch(() => {});
  }
  await page.waitForTimeout(600);
  await shot(page, "ug-02-12-parametry-analizy");
  await textBtn(page, /Uruchom analiz/).click();
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-13-postep-analizy");
  // czekaj na zakończenie (tekst na stronie) — do 6 min
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(6000);
    const done = await page.locator("text=/Analiza zakończona|nie powiodła/").count().catch(() => 0);
    if (done) { console.log("  analiza główna zakończona"); break; }
    if (i % 10 === 9) console.log(`  ...czekam na analizę (${(i + 1) * 6}s)`);
  }
});
await step("R6: preprocessing", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.locator("a:has-text('Preprocessing'), button:has-text('Preprocessing')").first().click();
  await page.waitForTimeout(2000);
  await shot(page, "ug-02-14-preprocessing", { fullPage: true });
});
await step("R6: wyniki — przegląd", async () => {
  await page.goto(`${card}/results`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-15-wyniki-przeglad");
});
await step("R6: błędy kodu", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.locator("a:has-text('Błędy kodu'), button:has-text('Błędy kodu')").first().click();
  await page.waitForTimeout(2000);
  await shot(page, "ug-02-16-bledy-kodu", { fullPage: true });
});
await step("R6: compliance", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.locator("a:has-text('Compliance'), button:has-text('Compliance')").first().click();
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-17-compliance", { fullPage: true });
});

// ============ ROZDZIAŁ 8 ============
await step("R8: diagram klas + porównanie z kodem", async () => {
  await page.goto(`${card}/uml`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator("a:has-text('Zobacz')").first().click();
  await page.waitForTimeout(2000);
  await shot(page, "ug-02-21-diagram-klas", { fullPage: true });
});
await step("R8: wynik GUI", async () => {
  await page.goto(`${card}/gui`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator("a:has-text('Zobacz wynik')").first().click();
  await page.waitForTimeout(2000);
  await shot(page, "ug-02-22-wynik-gui", { fullPage: true });
});
await step("R8: macierz śledzenia", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.locator("a:has-text('Macierz śledzenia'), button:has-text('Macierz śledzenia')").first().click();
  await page.waitForTimeout(1500);
  await textBtn(page, /Przebuduj macierz/).click().catch(() => {});
  await page.waitForTimeout(3000);
  await shot(page, "ug-02-23-macierz-sledzenia", { fullPage: true });
});

await browser.close();
console.log("✅ capture-ug-02 zakończony");
