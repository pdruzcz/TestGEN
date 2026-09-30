# Golden GUI — kategoria `real/` + `real_dense` (Story 3-14b, 3-14c)

Zrzuty **realnych, popularnych interfejsów** — fundament zbioru NFR-ACC-001
(„>80% dla 10 typów komponentów", 80+ screenshotów z GT; Story 3-14c domknęła
21 → **81 próbek**, z czego **63 realne**). Realne fonty, gradienty, gęste
layouty i szum OCR — to one obnażają detektor; syntetyk (18, ≤ 20) tylko
dorynkowuje typy słabo reprezentowane (modale).

## Licencje / legal

| Źródło | Licencja | Setup | Zrzuty |
|---|---|---|---|
| [Keycloak](https://www.keycloak.org) 26.7.1 — theme logowania | Apache-2.0 | lokalny `kc start-dev` | 3 (3-14b) |
| Keycloak 26.7.1 — admin console | Apache-2.0 | lokalny `kc start-dev` + bootstrap admina | 18 (3-14c) |
| [the-internet](https://the-internet.herokuapp.com) (Sauce Labs) | MIT | publiczna instancja | 10 |
| [Angular Material docs](https://material.angular.io) | MIT | publiczna (CDN) | 16 |
| [Bootstrap 5.3 docs](https://getbootstrap.com) | MIT | publiczna | 14 |
| [Mailpit](https://github.com/axllent/mailpit) | MIT | lokalny binarny serwer | 2 |

**Nie używamy** zrzutów popularnych, zastrzeżonych UI (Google, Facebook itp.) —
zastrzeżone znaki towarowe i design oznaczają ryzyko prawne **nawet w plikach
testowych** repo komercyjnego SaaS (konwencja z 3-14b).

## Przechwyt (narzędzie deweloperskie — NIE w CI; PNG commitowane)

```bash
# 1) Playwright (raz):
mkdir -p /tmp/pw && cd /tmp/pw && npm i playwright@1.62
# 2) Keycloak 26.7.1 (osobny terminal, Java 17+; bootstrap admina przy 1. starcie):
#    set KC_BOOTSTRAP_ADMIN_USERNAME=golden-admin
#    set KC_BOOTSTRAP_ADMIN_PASSWORD=golden-pass-123
#    kc start-dev --http-port=8080
# 3) Mailpit (opcjonalnie; UI domyślnie :8025, SMTP :1025) + kilka maili testowych
# 4) Przechwyt:
NODE_PATH=/tmp/pw/node_modules node backend/scripts/capture_real_ui.js \
  backend/tests/golden_data/gui/real
```

Uwagi operacyjne (zweryfikowane 2026-08-19):

- **Routing konsoli KC 26.7 jest haszowy** (`/admin/master/console/#/master/<strona>`)
  i **realm-selector NIE istnieje w mastheadzie** — zamiast niego strona
  „Manage realms" (`#/master/realms`; realm `golden` tworzy skrypt przez Admin
  REST API). Identity providers nie mają przycisku „Add provider" ani klikalnych
  kart — tylko widok spoczynkowy.
- Skrypt jest **idempotentny**: istniejące PNG są chronione (GT kurowane pod
  konkretne piksele); `CAPTURE_FORCE=1` nadpisuje (wtedy GT trzeba przekurować).
- heroku cold-start → wbudowany retry (×3–4); Material/Bootstrap po blokadzie CDN
  → fallback self-host (`npx serve` lokalnej kopii docs).
- Viewport 1280×800; wyjątek `keycloak_register` 1280×1024 (formularz dłuższy
  niż 800 px).

## Stany interakcji (AC6 3-14c)

Detektor musi widzieć typy w stanie „otwartym", nie tylko spoczynkowym. W zbiorze
są oznaczone tagiem w polu `description` GT (asercja w `test_gui_type_coverage`):

- **otwarty dropdown**: `material_select_open`, `bootstrap_dropdown_open`
- **otwarty modal**: `kc_admin_user_delete_modal`, `material_dialog_open`,
  `bootstrap_modal_open`
- **rozwinięte menu**: `kc_admin_users_kebab_open`, `kc_admin_user_menu_open`,
  `material_menu_open`
- (bonus) **przełączona zakładka**: `kc_admin_client_detail_roles_tab`,
  `kc_admin_realm_settings_login_tab`, `material_tabs_switched`

Natywne popupy (`<select>` the-internet) nie renderują się w zrzucie headless —
stany „otwarte" zapewniają overlaye CDK/Bootstrap/PatternFly.

## Ground truth — jak czytać

GT to **kurowany inwentarz prawdziwych komponentów** (co człowiek widzi na
ekranie), NIE surowy wynik detektora — detekcja zawyża 2–5× na realach i do
~12× na gęstych stronach docs (fragmenty tekstu OCR lecą jako `button`/
`checkbox`/`menu`). Szkice do kuracji robi `backend/scripts/gt_prefill.py`
(`*_prefill.json`, celowo poza discovery — po weryfikacji ręcznej zapis jako
`*_ground_truth.json`).

Widełki ratio detected/expected w `test_gui_png_golden.py` (cv2-gated):

| kategoria | podłoga | sufit | empiria 3-14c |
|---|---|---|---|
| `real` | 0.5 | 6.0 | 0.8–5.3 |
| `real_dense` (Bootstrap/Material docs, Mailpit, KC Sessions/Groups) | 0.5 | **15.0** | 7.2–12.3 (sufit ≈ 1.2× maksimum) |
| syntetyk | 0.5 | — | 0.6–1.0 |

Progi NFR-ACC-001 (>80%) **bez luzowania**; sufity bronią przed eksplozją
false-positive'ów, podłogi przed ślepotą.

Długoterminowy kierunek (follow-up): metryka per-komponent (IoU-matching GT↔
detekcji) zamiast porównania liczników.
