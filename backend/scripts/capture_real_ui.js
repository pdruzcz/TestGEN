/**
 * Przechwyt zrzutów realnych UI dla golden GUI — kategoria `real/` (Story 3-14b, 3-14c).
 *
 * Źródła (licencje w gui/real/README.md):
 *   - Keycloak 26.7.1 (Apache-2.0) — lokalny `kc start-dev`, realm master.
 *     Theme (3-14b): login, login-error, register. Admin console (3-14c):
 *     Clients/Users/Sessions/Realm settings/... + stany interakcji: rozwinięte
 *     kebab-menu, modal usuwania użytkownika, przełączona zakładka, menu
 *     użytkownika, otwarty dropdown „Add provider". Wymaga bootstrap admina
 *     (KC 26: `KC_BOOTSTRAP_ADMIN_USERNAME`/`KC_BOOTSTRAP_ADMIN_PASSWORD`
 *     przy PIERWSZYM starcie). UWAGA: konsola używa routingu haszowego
 *     (`/admin/master/console/#/master/<strona>`), a realm-selector w mastheadzie
 *     NIE istnieje w 26.7 — zamiast tego strona „Manage realms" (`#/master/realms`).
 *   - the-internet (MIT, Sauce Labs) — publiczna instancja herokuapp.
 *   - Angular Material docs (MIT) — material.angular.io, live demo komponentów.
 *   - Bootstrap 5.3 docs (MIT) — getbootstrap.com.
 *   - Mailpit (MIT) — opcjonalny, lokalny binarny serwer (UI domyślnie :8025).
 *
 * Uruchomienie (narzędzie deweloperskie, NIE wchodzi do CI):
 *   mkdir -p /tmp/pw && cd /tmp/pw && npm i playwright@1.62
 *   # Keycloak (osobny terminal; Java 17+), bootstrap admina przy 1. starcie:
 *   #   set KC_BOOTSTRAP_ADMIN_USERNAME=golden-admin
 *   #   set KC_BOOTSTRAP_ADMIN_PASSWORD=golden-pass-123
 *   #   kc start-dev --http-port=8080
 *   NODE_PATH=/tmp/pw/node_modules node backend/scripts/capture_real_ui.js \
 *     backend/tests/golden_data/gui/real
 *
 * Domyślnie istniejące PNG są CHRONIONE (GT z 3-14b kurowane pod konkretne
 * piksele); CAPTURE_FORCE=1 nadpisuje wszystko (wtedy GT trzeba przekurować).
 *
 * Viewport: 1280×800 (zgodny z konwencją golden GUI; wyjątki dłuższych
 * formularzy udokumentowane w GT — keycloak_register 1280×1024).
 */

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const OUT = process.argv[2] || ".";
const FORCE = process.env.CAPTURE_FORCE === "1";
const VIEWPORT = { width: 1280, height: 800 };
const KEYCLOAK = process.env.KEYCLOAK_URL || "http://localhost:8080";
const KC_ADMIN_USER = process.env.KC_ADMIN_USER || "golden-admin";
const KC_ADMIN_PASS = process.env.KC_ADMIN_PASS || "golden-pass-123";
const INTERNET = "https://the-internet.herokuapp.com";
const MATERIAL = "https://material.angular.io";
const BOOTSTRAP = "https://getbootstrap.com";
const MAILPIT = process.env.MAILPIT_URL || "http://localhost:8025";

// Każda sekcja działa niezależnie — błąd jednej strony nie zrywa całego przechwytu
// (T2 i tak robi selekcję; tu zbieramy kandydatów).
const results = { captured: [], skipped: [], failed: [] };

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: VIEWPORT });

  const shot = async (name) => {
    const file = path.join(OUT, `${name}.png`);
    if (!FORCE && fs.existsSync(file)) {
      results.skipped.push(name);
      return false;
    }
    await page.screenshot({ path: file });
    results.captured.push(name);
    return true;
  };

  // goto z retry (heroku cold-start, CDN) + krótkie ustatycznienie animacji.
  const goto = async (url, opts = {}) => {
    const tries = opts.tries ?? 3;
    for (let i = 1; i <= tries; i++) {
      try {
        await page.goto(url, { waitUntil: "networkidle", timeout: 45000 });
        await page.waitForTimeout(opts.settle ?? 600);
        return true;
      } catch (e) {
        if (i === tries) throw e;
        await page.waitForTimeout(3000 * i);
      }
    }
    return false;
  };

  // Selektory OSOBNO per silnik — mieszanie `css, text=...` w jednym stringu
  // nie parsuje się w Playwright. Zwraca pierwszy, który zadziałał.
  const clickFirst = async (selectors, timeout = 6000) => {
    for (const sel of selectors) {
      try {
        await page.locator(sel).first().click({ timeout });
        return sel;
      } catch {
        /* próbuj następny */
      }
    }
    throw new Error(`no clickable selector: ${selectors.join(", ")}`);
  };

  const waitForFirst = async (selectors, timeout = 6000) => {
    for (const sel of selectors) {
      try {
        await page.locator(sel).first().waitFor({ timeout, state: "visible" });
        return sel;
      } catch {
        /* próbuj następny */
      }
    }
    throw new Error(`no visible selector: ${selectors.join(", ")}`);
  };

  const section = async (label, fn) => {
    try {
      await fn();
    } catch (e) {
      results.failed.push(`${label}: ${e.message}`);
    }
  };

  // ════════════════════════════════════════════════════════════════════
  // 1. Keycloak REST — bootstrap stanu (idempotentny):
  //    registrationAllowed (konwencja 3-14b), realm `golden` (tablica
  //    „Manage realms" ma 2 wiersze), użytkownik `golden-test` (kebab +
  //    modal usuwania targetują konkretny wiersz, NIE konto admina).
  // ════════════════════════════════════════════════════════════════════
  await section("kc-rest-bootstrap", async () => {
    const tokenResp = await fetch(`${KEYCLOAK}/realms/master/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: "admin-cli",
        grant_type: "password",
        username: KC_ADMIN_USER,
        password: KC_ADMIN_PASS,
      }),
    });
    if (!tokenResp.ok) throw new Error(`token: ${tokenResp.status}`);
    const { access_token } = await tokenResp.json();
    const auth = { "Content-Type": "application/json", Authorization: `Bearer ${access_token}` };

    const put = await fetch(`${KEYCLOAK}/admin/realms/master`, {
      method: "PUT",
      headers: auth,
      body: JSON.stringify({ registrationAllowed: true }),
    });
    if (!put.ok) throw new Error(`realm update: ${put.status}`);

    // Realm golden — 409 = już istnieje, to nie błąd.
    await fetch(`${KEYCLOAK}/admin/realms`, {
      method: "POST",
      headers: auth,
      body: JSON.stringify({ realm: "golden", enabled: true }),
    });

    // Użytkownik golden-test — 409 = już istnieje.
    const user = await fetch(`${KEYCLOAK}/admin/realms/master/users`, {
      method: "POST",
      headers: auth,
      body: JSON.stringify({ username: "golden-test", enabled: true }),
    });
    if (!user.ok && user.status !== 409) throw new Error(`user: ${user.status}`);
  });

  // ════════════════════════════════════════════════════════════════════
  // 2. Keycloak — strona logowania (3-14b, regenerowalne)
  // ════════════════════════════════════════════════════════════════════
  await section("kc-theme", async () => {
    await goto(`${KEYCLOAK}/admin/master/console/`);
    await page.waitForSelector("#username", { timeout: 20000 });
    await shot("keycloak_login");

    // Stan błędu (błędne dane) — KC 26 (PatternFly): markup alertu zmienny.
    await page.fill("#username", "golden-test");
    await page.fill("#password", "wrong-password");
    await page.click("#kc-login");
    try {
      await waitForFirst(
        [
          ".pf-v5-c-alert",
          ".pf-c-alert",
          "#input-error",
          "#kc-error-message",
          "text=Invalid username",
        ],
        5000,
      );
    } catch {
      await page.waitForTimeout(2500);
    }
    await shot("keycloak_login_error");
  });

  await section("kc-register", async () => {
    // Formularz rejestracji dłuższy niż 800 px — wyższy viewport (jak 3-14b).
    await page.setViewportSize({ width: VIEWPORT.width, height: 1024 });
    await goto(`${KEYCLOAK}/admin/master/console/`);
    await page.waitForSelector("#username", { timeout: 20000 });
    await page.click('a:has-text("Register")');
    await page.waitForSelector("#firstName", { timeout: 10000 });
    await shot("keycloak_register");
    await page.setViewportSize(VIEWPORT);
  });

  // ════════════════════════════════════════════════════════════════════
  // 3. Keycloak admin console — logowanie + strony + stany interakcji
  // ════════════════════════════════════════════════════════════════════
  await section("kc-admin-login", async () => {
    await goto(`${KEYCLOAK}/admin/master/console/`);
    await page.waitForSelector("#username", { timeout: 20000 });
    await page.fill("#username", KC_ADMIN_USER);
    await page.fill("#password", KC_ADMIN_PASS);
    await page.click("#kc-login");
    // React console ładuje się po redirect — czekaj na nawigację boczną.
    await page.locator("nav").first().waitFor({ timeout: 30000, state: "visible" });
    await page.waitForTimeout(2500);
  });

  // Routing konsoli: haszowy, np. /admin/master/console/#/master/clients
  const adminPage = async (name, route, waitSels) => {
    await section(name, async () => {
      await goto(`${KEYCLOAK}/admin/master/console/#/master/${route}`);
      await waitForFirst(waitSels, 15000);
      await page.waitForTimeout(800);
      await shot(name);
    });
  };

  const TABLE_WAIT = ["table", ".pf-v5-c-table", '[role="grid"]'];
  await adminPage("kc_admin_clients", "clients", TABLE_WAIT);
  await adminPage("kc_admin_users", "users", TABLE_WAIT);
  await adminPage("kc_admin_sessions", "sessions", TABLE_WAIT);
  await adminPage("kc_admin_realm_list", "realms", TABLE_WAIT);
  await adminPage("kc_admin_roles", "roles", TABLE_WAIT);
  await adminPage("kc_admin_client_scopes", "client-scopes", TABLE_WAIT);
  await adminPage("kc_admin_authentication", "authentication", TABLE_WAIT);
  await adminPage("kc_admin_events", "events", [".pf-v5-c-empty-state", ...TABLE_WAIT]);
  await adminPage("kc_admin_groups", "groups", [
    'button:has-text("Create group")',
    ".pf-v5-c-empty-state",
    ...TABLE_WAIT,
  ]);
  // KC 26.7: brak przycisku „Add provider" — strona to siatka kart providerów.
  await adminPage("kc_admin_identity_providers", "identity-providers", [
    'a:has-text("Keycloak OpenID Connect")',
    ".pf-v5-c-card",
    ".pf-v5-c-empty-state",
    ...TABLE_WAIT,
  ]);
  await adminPage("kc_admin_realm_settings", "realm-settings", [
    ".pf-v5-c-tabs",
    '[role="tablist"]',
  ]);

  // Szczegół klienta (security-admin-console) — zakładki + form Settings.
  await section("kc_admin_client_detail", async () => {
    await goto(`${KEYCLOAK}/admin/master/console/#/master/clients`);
    await waitForFirst(TABLE_WAIT, 15000);
    await page.locator('a:has-text("security-admin-console")').first().click();
    await waitForFirst(['[role="tablist"]', ".pf-v5-c-tabs"], 15000);
    await page.waitForTimeout(1000);
    await shot("kc_admin_client_detail");

    // Stan interakcji: przełączona zakładka (Roles).
    await page.locator('[role="tab"]:has-text("Roles")').first().click();
    await page.waitForTimeout(1000);
    await shot("kc_admin_client_detail_roles_tab");
  });

  // Stan interakcji: zakładka Realm settings → Login.
  await section("kc_admin_realm_settings_login_tab", async () => {
    await goto(`${KEYCLOAK}/admin/master/console/#/master/realm-settings`);
    await waitForFirst([".pf-v5-c-tabs", '[role="tablist"]'], 15000);
    await page.locator('[role="tab"]:has-text("Login")').first().click();
    await page.waitForTimeout(1200);
    await shot("kc_admin_realm_settings_login_tab");
  });

  // Formularz dodawania użytkownika — SAM PODGLĄD (bez submit; Cancel).
  await section("kc_admin_user_create_form", async () => {
    await goto(`${KEYCLOAK}/admin/master/console/#/master/users`);
    await waitForFirst(TABLE_WAIT, 15000);
    await page.locator('button:has-text("Add user")').first().click();
    await waitForFirst(['input[name="username"]', "form", ".pf-v5-c-form"], 10000);
    await page.fill('input[name="username"]', "golden-preview");
    await page.waitForTimeout(600);
    await shot("kc_admin_user_create_form");
    await clickFirst(
      ['button:has-text("Cancel")', '.pf-v5-c-form button:has-text("Cancel")'],
      4000,
    ).catch(() => page.keyboard.press("Escape"));
  });

  // Stan interakcji: rozwinięte kebab-menu wiersza golden-test (NIE admina).
  const openUserKebab = async () => {
    await goto(`${KEYCLOAK}/admin/master/console/#/master/users`);
    await waitForFirst(TABLE_WAIT, 15000);
    await page.locator('tr:has-text("golden-test") [aria-label="Kebab toggle"]').first().click({
      timeout: 10000,
    });
    await waitForFirst(['.pf-v5-c-menu', '[role="menu"]'], 5000);
    await page.waitForTimeout(500);
  };

  await section("kc_admin_users_kebab_open", async () => {
    await openUserKebab();
    await shot("kc_admin_users_kebab_open");
    await page.keyboard.press("Escape");
  });

  // Stan interakcji: modal potwierdzenia usunięcia (Cancel — nic nie usuwamy).
  await section("kc_admin_user_delete_modal", async () => {
    await openUserKebab();
    await page.locator('.pf-v5-c-menu__item:has-text("Delete")').first().click();
    await waitForFirst(['.pf-v5-c-modal-box', '[role="dialog"]'], 5000);
    await page.waitForTimeout(500);
    await shot("kc_admin_user_delete_modal");
    await clickFirst(
      ['.pf-v5-c-modal-box button:has-text("Cancel")', 'button:has-text("Cancel")'],
      4000,
    ).catch(() => page.keyboard.press("Escape"));
  });

  // Stan interakcji: menu użytkownika w mastheadzie (rozwinięte menu).
  await section("kc_admin_user_menu_open", async () => {
    await goto(`${KEYCLOAK}/admin/master/console/#/master/clients`);
    await waitForFirst(TABLE_WAIT, 15000);
    await page.locator(`.pf-v5-c-menu-toggle:has-text("${KC_ADMIN_USER}")`).first().click();
    await waitForFirst(['.pf-v5-c-menu', '[role="menu"]'], 5000);
    await page.waitForTimeout(500);
    await shot("kc_admin_user_menu_open");
    await page.keyboard.press("Escape");
  });

  // UWAGA (KC 26.7): Identity providers nie mają ani dropdownu „Add provider",
  // ani klikalnych kart (karty w niewidocznym kontenerze — klik timeoutuje);
  // strona łapie się tylko jako widok spoczynkowy (kc_admin_identity_providers).

  // ════════════════════════════════════════════════════════════════════
  // 4. the-internet — strony z 3-14b (chronione) + nowe (3-14c)
  // ════════════════════════════════════════════════════════════════════
  await section("internet-login", async () => {
    await goto(`${INTERNET}/login`, { tries: 4 });
    await shot("internet_login");
  });
  await section("internet-tables", async () => {
    await goto(`${INTERNET}/tables`, { tries: 4 });
    await page.waitForTimeout(500); // render tabeli (JSort)
    await shot("internet_tables");
  });
  await section("internet-dynamic-controls", async () => {
    await goto(`${INTERNET}/dynamic_controls`, { tries: 4 });
    await page.waitForSelector("#checkbox", { timeout: 10000 });
    await shot("internet_dynamic_controls");
  });
  await section("internet-checkboxes", async () => {
    await goto(`${INTERNET}/checkboxes`, { tries: 4 });
    await page.waitForSelector('input[type="checkbox"]', { timeout: 10000 });
    await shot("internet_checkboxes");
  });
  await section("internet-dropdown", async () => {
    // Natywny <select> — stan spoczynkowy (natywne popupy nie renderują się w
    // zrzucie headless; „otwarty dropdown" w stanie realnym zapewniają
    // Material select / Bootstrap dropdown / KC IdP provider).
    await goto(`${INTERNET}/dropdown`, { tries: 4 });
    await page.waitForSelector("#dropdown", { timeout: 10000 });
    await shot("internet_dropdown");
  });
  await section("internet-inputs", async () => {
    await goto(`${INTERNET}/inputs`, { tries: 4 });
    await page.waitForSelector('input[type="number"]', { timeout: 10000 });
    await shot("internet_inputs");
  });
  await section("internet-add-remove", async () => {
    await goto(`${INTERNET}/add_remove_elements/`, { tries: 4 });
    await page.waitForSelector('button:has-text("Add Element")', { timeout: 10000 });
    // Kilka dynamicznych przycisków Delete — gęstszy zestaw buttonów.
    for (let i = 0; i < 3; i++) await page.click('button:has-text("Add Element")');
    await page.waitForTimeout(300);
    await shot("internet_add_remove_elements");
  });
  await section("internet-hovers", async () => {
    await goto(`${INTERNET}/hovers`, { tries: 4 });
    await page.waitForSelector(".figure", { timeout: 10000 });
    // Hover odsłania linki „View profile" (stan interakcji).
    await page.locator(".figure").first().hover();
    await page.waitForTimeout(400);
    await shot("internet_hovers");
  });
  await section("internet-upload", async () => {
    await goto(`${INTERNET}/upload`, { tries: 4 });
    await page.waitForSelector('#file-upload, input[type="file"]', { timeout: 10000 });
    await shot("internet_upload");
  });
  await section("internet-forgot-password", async () => {
    await goto(`${INTERNET}/forgot_password`, { tries: 4 });
    await page.waitForSelector("#email, form", { timeout: 10000 });
    await shot("internet_forgot_password");
  });

  // ════════════════════════════════════════════════════════════════════
  // 5. Angular Material docs — live demo komponentów (MIT)
  // ════════════════════════════════════════════════════════════════════
  const materialPage = async (name, comp, waitSels) => {
    await section(name, async () => {
      await goto(`${MATERIAL}/components/${comp}/examples`, { tries: 3, settle: 1200 });
      await waitForFirst([...waitSels, "example-viewer"], 20000);
      await page.waitForTimeout(900);
      await shot(name);
    });
  };

  await materialPage("material_button", "button", [
    ".mat-mdc-button",
    ".mat-mdc-unelevated-button",
  ]);
  await materialPage("material_checkbox", "checkbox", [
    ".mat-mdc-checkbox",
    "mat-checkbox",
  ]);
  await materialPage("material_radio", "radio", [
    ".mat-mdc-radio-button",
    "mat-radio-button",
  ]);
  await materialPage("material_table", "table", [
    ".mat-mdc-table",
    "mat-table",
  ]);
  await materialPage("material_tabs", "tabs", [".mat-mdc-tab-group", "mat-tab-group"]);
  await materialPage("material_form_field", "form-field", [
    ".mat-mdc-form-field",
    "mat-form-field",
  ]);
  await materialPage("material_select", "select", [".mat-mdc-select", "mat-select"]);
  await materialPage("material_menu", "menu", [".mat-mdc-menu-trigger"]);
  await materialPage("material_dialog", "dialog", ["button"]);
  await materialPage("material_autocomplete", "autocomplete", [
    "input[matAutocomplete]",
    ".mat-mdc-autocomplete",
  ]);
  await materialPage("material_datepicker", "datepicker", [
    "mat-datepicker-toggle",
    ".mat-mdc-datepicker-toggle",
  ]);
  await materialPage("material_tooltip", "tooltip", ["button"]);

  // Stany interakcji Material (overlay CDK renderuje się w prawdziwym DOM).
  await section("material_select_open", async () => {
    await goto(`${MATERIAL}/components/select/examples`, { tries: 3, settle: 1200 });
    await waitForFirst([".mat-mdc-select"], 20000);
    await page.locator(".mat-mdc-select").first().click();
    await waitForFirst([".cdk-overlay-pane mat-option", ".mat-mdc-select-panel"], 5000);
    await page.waitForTimeout(500);
    await shot("material_select_open");
    await page.keyboard.press("Escape");
  });
  await section("material_menu_open", async () => {
    await goto(`${MATERIAL}/components/menu/examples`, { tries: 3, settle: 1200 });
    await waitForFirst([".mat-mdc-menu-trigger"], 20000);
    await page.locator(".mat-mdc-menu-trigger").first().click();
    await waitForFirst([".mat-mdc-menu-panel"], 5000);
    await page.waitForTimeout(500);
    await shot("material_menu_open");
    await page.keyboard.press("Escape");
  });
  await section("material_dialog_open", async () => {
    await goto(`${MATERIAL}/components/dialog/examples`, { tries: 3, settle: 1200 });
    await page.waitForSelector("example-viewer", { timeout: 20000 });
    // Przyciski „Open dialog (without animation/slowly)" — dowolny otwiera dialog.
    await page.locator('example-viewer button:has-text("Open dialog")').first().click();
    await waitForFirst([".mat-mdc-dialog-container"], 5000);
    await page.waitForTimeout(500);
    await shot("material_dialog_open");
    await page.keyboard.press("Escape");
  });
  await section("material_tabs_switched", async () => {
    await goto(`${MATERIAL}/components/tabs/examples`, { tries: 3, settle: 1200 });
    await waitForFirst([".mat-mdc-tab-group"], 20000);
    // Druga zakładka pierwszej grupy — stan „przełączona".
    await page.locator(".mat-mdc-tab-group .mat-mdc-tab").nth(1).click();
    await page.waitForTimeout(800);
    await shot("material_tabs_switched");
  });

  // ════════════════════════════════════════════════════════════════════
  // 6. Bootstrap 5.3 docs (MIT)
  // ════════════════════════════════════════════════════════════════════
  const bsPage = async (name, route, waitSels) => {
    await section(name, async () => {
      await goto(`${BOOTSTRAP}/docs/5.3/${route}`, { tries: 3 });
      await waitForFirst(waitSels, 15000);
      await page.waitForTimeout(700);
      await shot(name);
    });
  };

  await bsPage("bootstrap_forms", "forms/layout/", ["form", ".bd-example"]);
  await bsPage("bootstrap_forms_checks_radios", "forms/checks-radios/", [
    'input[type="checkbox"]',
    'input[type="radio"]',
  ]);
  await bsPage("bootstrap_forms_select", "forms/select/", ["form select", ".form-select"]);
  await bsPage("bootstrap_forms_input_group", "forms/input-group/", [
    ".input-group",
    ".form-control",
  ]);
  await bsPage("bootstrap_buttons", "examples/", [
    'button:has-text("Primary")',
    ".btn",
  ]);
  await bsPage("bootstrap_dropdowns", "components/dropdowns/", [
    ".dropdown-toggle",
    ".btn-group",
  ]);
  await bsPage("bootstrap_modal", "components/modal/", ["[data-bs-toggle='modal']"]);
  await bsPage("bootstrap_nav_tabs", "components/navs-tabs/", [".nav-tabs", ".nav"]);
  await bsPage("bootstrap_navbar", "components/navbar/", [".navbar"]);
  await bsPage("bootstrap_tables", "content/tables/", ["table"]);
  await bsPage("bootstrap_list_group", "components/list-group/", [".list-group"]);

  // Stany interakcji Bootstrap (prawdziwy DOM, nie natywny popup).
  await section("bootstrap_dropdown_open", async () => {
    await goto(`${BOOTSTRAP}/docs/5.3/components/dropdowns/`, { tries: 3 });
    await page.waitForSelector(".dropdown-toggle", { timeout: 15000 });
    await page.locator(".bd-example .dropdown-toggle").first().click();
    await waitForFirst([".dropdown-menu.show"], 5000);
    await page.waitForTimeout(500);
    await shot("bootstrap_dropdown_open");
    await page.keyboard.press("Escape");
  });
  await section("bootstrap_modal_open", async () => {
    await goto(`${BOOTSTRAP}/docs/5.3/components/modal/`, { tries: 3 });
    await page.waitForSelector("[data-bs-toggle='modal']", { timeout: 15000 });
    await page.locator(".bd-example [data-bs-toggle='modal']").first().click();
    await waitForFirst([".modal.show"], 5000);
    await page.waitForTimeout(500);
    await shot("bootstrap_modal_open");
    await page.keyboard.press("Escape");
  });
  await section("bootstrap_collapse_open", async () => {
    await goto(`${BOOTSTRAP}/docs/5.3/components/collapse/`, { tries: 3 });
    // Selektor scope'owany do przykładu — pierwszy niescope'owany match to
    // ukryty na desktopie toggle spisu treści (d-md-none).
    await page.waitForSelector('.bd-example [data-bs-toggle="collapse"]', { timeout: 15000 });
    await page.locator('.bd-example [data-bs-toggle="collapse"]').first().click();
    await waitForFirst([".collapse.show"], 5000);
    await page.waitForTimeout(500);
    await shot("bootstrap_collapse_open");
  });

  // ════════════════════════════════════════════════════════════════════
  // 7. Mailpit (MIT) — opcjonalny lokalny serwer (pomijany, jeśli nie wstaje)
  // ════════════════════════════════════════════════════════════════════
  await section("mailpit", async () => {
    const reachable = await fetch(MAILPIT, { signal: AbortSignal.timeout(3000) })
      .then((r) => r.ok)
      .catch(() => false);
    if (!reachable) throw new Error(`${MAILPIT} unreachable — sekcja pominięta`);

    await goto(`${MAILPIT}/`);
    await page.waitForSelector("table, .navbar", { timeout: 10000 });
    await shot("mailpit_messages");

    // Widok wiadomości — tabela nagłówków + treść.
    await page.locator("table tbody tr").first().click().catch(() => {});
    await waitForFirst([".message", "dl", "iframe"], 5000).catch(() => {});
    await page.waitForTimeout(800);
    await shot("mailpit_message");

    // Rozwinięte menu w toolbarze Mailpita (np. „Refresh").
    await goto(`${MAILPIT}/`);
    await page.waitForSelector(".navbar", { timeout: 10000 });
    const menuClicked = await clickFirst(
      [".navbar .dropdown-toggle", '[data-toggle="dropdown"]', ".btn-group .dropdown-toggle"],
      4000,
    ).catch(() => null);
    if (menuClicked) {
      await waitForFirst([".dropdown-menu.show"], 5000).catch(() => {});
      await page.waitForTimeout(500);
      await shot("mailpit_menu_open");
    }
  });

  await browser.close();

  const n = results.captured.length;
  console.log(`OK: ${n} nowych zrzutów → ${path.resolve(OUT)}`);
  if (results.skipped.length) console.log(`  pominięte (istnieją): ${results.skipped.length}`);
  if (results.failed.length) {
    console.log(`  nieudane sekcje (${results.failed.length}):`);
    for (const f of results.failed) console.log(`    - ${f}`);
    process.exitCode = 2; // częściowy przechwyt — do obejrzenia w T2
  }
}

main().catch((err) => {
  console.error("Capture failed:", err.message);
  process.exit(1);
});
