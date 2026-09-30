# Budowanie APK TestGEN (Android)

Powłoka mobilna (Story 6.12): Flutter **WebView** ładujący frontend Angular
z serwera + mostek `FlutterBridgeService` (redirecty tpay/3DS przez
`url_launcher`, deep linki przez `app_links`).

## Środowiska

URL serwera wybierasz **przy budowie** (`--dart-define`), bez edycji kodu:

```bash
# PRODUKCJA — https://test-gen.pl (realna bramka tpay; domena w trakcie stawiania):
flutter build apk --release

# ŚRODOWISKO TESTOWE — https://testgen.nexio.pl (tpay sandbox):
flutter build apk --release --dart-define=TESTGEN_URL=https://testgen.nexio.pl

# praca lokalna (debug/profile zawsze ładują http://localhost:4200):
flutter run --debug
```

Oba APK-i mają tę samą tożsamość (`pl.testgen.app`) — instalacja jednego
**zastępuje** drugi (odinstaluj przed zmianą środowiska, żeby WebView nie
trzymało ciasteczek poprzedniego).

## Tożsamość aplikacji

- `applicationId`/`namespace`: **`pl.testgen.app`** — Java nie dopuszcza
  myślników w nazwach pakietów, stąd nie `pl.test-gen.*`; marka test-gen.pl.
- Etykieta launchera: **TestGEN**; ikona: znak z `frontend/assets/logo.svg`
  (turkus na białym; regeneracja: `dart run flutter_launcher_icons`,
  źródła w `mobile/assets/icon*.png|svg`).
- Deep link: schemat `testgen://` (intent-filter w `AndroidManifest.xml`);
  powroty z bramki tpay muszą mieć zarejestrowany URL powrotu w panelu
  tpay danego środowiska.

## Build

```bash
cd mobile
flutter pub get
flutter build apk --release   # APK: build/app/outputs/flutter-apk/app-release.apk
# smoke-test toolchaina bez podpisu:
flutter build apk --debug
```

Wymagania: Flutter SDK + Android SDK/JDK 17 (`flutter` w PATH na stacji
 deweloperskiej — zweryfikowano 2026-09-30).

## Podpis release — PROBLEM NA POTEM

Dopóki nie ma `android/key.properties` + keystore'a, release podpisuje się
**kluczem debug** (warunkowy `signingConfig` w `app/build.gradle.kts`).
Do sideloadu/wewnętrznej dystrybucji wystarcza. **Przed Google Play:**

1. `keytool -genkey -v -keystore testgen-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias testgen`
2. skopiuj `android/key.properties.example` → `android/key.properties`
   i uzupełnij (plik oraz `*.jks` są gitignored — nigdy do repo),
3. `flutter build apk --release` — podpisze się produkcyjnie,
4. keystore **archiwizuj** (strata = koniec aktualizacji pod tym ID).

## Otwarte follow-upy

- **HTTPS na test-gen.pl** — release-WebView nie łyknie self-signed;
  ważny certyfikat = warunek pierwszego uruchomienia produkcyjnego.
- **Google Play** (opcjonalnie, później): konto 25 USD,
  `flutter build appbundle`, target API wg wymogów sklepu, polityka
  prywatności (test-gen.pl/polityka).
