# Powłoka Flutter WebView (mobile/desktop)

> Dokumentacja P2, Epic 6 — Story 6-12.
> Implementacja: `mobile/` (projekt `testgen_mobile`), mostek po stronie
> Angulara: `shared/services/flutter-bridge.service.ts`.

## 1. Koncepcja

Natywna powłoka uruchamia **frontend webowy w WebView** — minimalna
logika natywna, cały interfejs i logika po stronie Angulara. Jedna baza
funkcjonalna (web) + dystrybucja przez sklepy/systemy (aplikacja natywna).

## 2. Platformy

| Platforma | WebView | Plugin |
|---|---|---|
| iOS 15+ | WKWebView | `webview_flutter` |
| Android | Android WebView | `webview_flutter` |
| Windows | Edge WebView2 | `webview_windows` |
| Linux | fallback: przeglądarka systemowa | `url_launcher` (brak stabilnego pluginu WebKitGTK) |

## 3. Struktura (`mobile/lib/`)

```
main.dart                            # entry point
config.dart                          # URL frontendu (dev/prod)
webview/webview_container.dart       # dobór WebView per platforma + ekran offline
bridge/js_bridge.dart                # dwukierunkowy mostek JS ↔ Dart
deep_link/deep_link_handler.dart     # testgen:// → ścieżka Angulara
notifications/notification_handler.dart  # payload powiadomienia → nawigacja
widgets/offline_message.dart         # komunikat braku sieci
```

## 4. Mostek JS (`js_bridge.dart` ↔ `flutter-bridge.service.ts`)

Dwukierunkowa komunikacja WebView ↔ Flutter:

- **Angular → natywne**: żądania funkcji powłoki (np. obsługa linków
  zewnętrznych, udostępnienie plików PDF),
- **natywne → Angular**: zdarzenia systemowe, deep linki, powiadomienia.

`flutter-bridge.service.ts` wykrywa, czy aplikacja działa w powłoce —
poza nią funkcje mostka są no-op (czysty web działa bez zmian).

## 5. Deep linki i powiadomienia

- **Deep link** `testgen://ścieżka` → `deep_link_handler` tłumaczy na
  nawigację routera Angulara (np. link z maila otwiera konkretny projekt),
- **powiadomienia push/lokalne** → `notification_handler` przekazuje
  payload do Angulara, który nawiguje na właściwy ekran (np. powiadomienie
  o progu limitu → dashboard zużycia).

## 6. Tryb offline

`webview_container` + `widgets/offline_message.dart` — wykrycie braku
sieci pokazuje natywny komunikat; po powrocie połączenia WebView odświeża
frontend. Cache'owanie treści świadomie minimalne (dane tenanta nie trafiają
do pamięci podręcznej powłoki).

## 7. Konfiguracja i budowa

`config.dart` trzyma URL frontendu osobno dla dev i prod; budowa per
platforma standardowymi narzędziami Flutter (`flutter build apk/ios/ipa/
windows`). Powłoka nie przechowuje sekretów — uwierzytelnienie wyłącznie
przez sesję webową (HttpOnly cookies) w WebView.
