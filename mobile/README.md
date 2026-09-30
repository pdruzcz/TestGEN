# TestGEN — Flutter WebView shell (Story 6.12)

Natywna powłoka mobile/desktop dla aplikacji Angular TestGEN. Minimalna
logika natywna — cały interfejs pochodzi z frontendu webowego uruchamianego
w WebView.

## Platformy

| Platforma | WebView            | Plugin            |
| --------- | ------------------ | ----------------- |
| iOS 15+   | WKWebView          | `webview_flutter` |
| Android   | Android WebView    | `webview_flutter` |
| Windows   | Edge WebView2      | `webview_windows` |
| Linux     | fallback: przeglądarka systemowa (`url_launcher`) — brak stabilnego pluginu WebKitGTK dla webview_flutter |

## Architektura

```
lib/
  main.dart                            # entry point
  config.dart                          # URL frontendu (dev/prod)
  webview/webview_container.dart       # dobór WebView per platforma + offline (AC6)
  bridge/js_bridge.dart                # dwukierunkowy JS bridge (AC5/AC7)
  deep_link/deep_link_handler.dart     # testgen:// -> ścieżka Angulara (AC5)
  notifications/notification_handler.dart  # payload powiadomienia -> nawigacja (AC7)
  widgets/offline_message.dart         # "Brak połączenia z serwerem..." + Ponów
```

### JS bridge

- **Flutter → Angular**: wykonanie skryptu `window.testgenBridge.*`
  (rejestrowany przez `FlutterBridgeService` w
  `frontend/src/app/shared/services/flutter-bridge.service.ts`):
  `navigateTo(url)`, `receiveNotification(data)`, `setDeviceInfo(info)`.
- **Angular → Flutter**: `window.flutter_bridge.postMessage(json)`
  (JavaScriptChannel, iOS/Android) lub `window.chrome.webview.postMessage(json)`
  (WebView2, Windows). Format: `{"type": "...", "payload": {...}}`.
  Obsługiwane typy: `getDeviceInfo`, `openExternal`, `share`.

### Deep linking

Schemat `testgen://` zarejestrowany w `AndroidManifest.xml` (intent-filter)
oraz `ios/Runner/Info.plist` (CFBundleURLTypes). Obsługiwane ścieżki:
`projects`, `analysis`, `reports`, `dashboard` —
np. `testgen://analysis/123` → nawigacja Angulara do `/analysis/123`.

### Powiadomienia push (AC7)

`NotificationHandler` tłumaczy payload `{"deepLink": "testgen://..."}` na
nawigację przez JS bridge. Transport (FCM na iOS/Android, WNS na Windows)
wymaga konfiguracji projektu Firebase (`google-services.json`,
`GoogleService-Info.plist`) oraz rejestracji WNS — do podpięcia po
udostępnieniu projektu Firebase (dodać `firebase_messaging` i wywołać
`NotificationHandler.handleNotificationTap` z `onMessageOpenedApp`).

## Development

```bash
flutter pub get
flutter analyze
flutter test
flutter run            # z uruchomionym frontendem: cd ../frontend && npm start
```

W trybie debug shell ładuje `http://localhost:4200`, w release —
`https://app.testgen.io` (patrz `lib/config.dart`).

## Buildy release (AC8 — budżety rozmiaru)

| Artefakt          | Budżet  | Komenda |
| ----------------- | ------- | ------- |
| APK (Android)     | < 30 MB | `flutter build apk --release --split-per-abi --obfuscate --split-debug-info=build/symbols` |
| IPA (iOS)         | < 50 MB | `flutter build ipa --release --obfuscate --split-debug-info=build/symbols` |
| Windows installer | < 60 MB | `flutter build windows --release` + pakowanie (np. Inno Setup / MSIX) |
| Linux             | —       | `flutter build linux --release` |

Optymalizacje: tree-shaking ikon (domyślny), `--split-debug-info`
(symbole poza binarką), `--obfuscate`, `--split-per-abi` (osobne APK per
architektura). Rozmiary weryfikować po buildzie: `ls -lh build/...`.
