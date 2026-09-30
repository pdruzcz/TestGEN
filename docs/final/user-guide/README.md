# Podręcznik użytkownika — indeks

> Poradniki „jak korzystać" per moduł platformy. Wszystkie ekrany
> dostępne także z aplikacji mobilnej (Flutter WebView) — patrz
> [architecture/interfejs-webowy/07-shell-flutter.md](../architecture/interfejs-webowy/07-shell-flutter.md).

## Spis poradników

| Część podręcznika | Zakres | Status |
|---|---|---|
| [**Część 1 — Wprowadzenie i szybki start**](01-wprowadzenie.md) | o platformie, plany, rejestracja → pierwszy raport w ~20 minut, interfejs, dostępność — start tutaj | ✅ gotowa |
| [Część 2 — Projekty i analiza](02-projekty-i-analiza.md) | zakładanie projektów, upload plików, konfiguracja i uruchamianie analiz | ✅ gotowa |
| [Część 3 — Zaawansowane funkcje](03-testy-bezpieczenstwo-eksport.md) | integracje (Jira, Azure DevOps, GitHub/GitLab, CI/CD, TestRail/Xray/Zephyr, import z Jiry), API, klucze API, CLI, webhooki, dostępność | ✅ gotowa |
| [Część 4 — Administracja i rozwiązywanie problemów](04-integracje-ustawienia-faq.md) | konto i subskrypcja, bezpieczeństwo i klucze API, FAQ, troubleshooting, wsparcie | ✅ gotowa |


Poradniki per moduł:

| Moduł | Poradniki | Zakres |
|---|---|---|
| [Interfejs webowy](interfejs-webowy/01-nawigacja-i-ekrany.md) | [nawigacja](interfejs-webowy/01-nawigacja-i-ekrany.md) · [projekty i upload](interfejs-webowy/02-projekty-i-upload.md) · [wyniki i test case'y](interfejs-webowy/03-wyniki-i-test-case-y.md) · [raporty i eksport](interfejs-webowy/04-raporty-i-eksport.md) · [dostępność](interfejs-webowy/05-dostepnosc.md) | dashboard, projekty, upload drag & drop, przeglądarka wyników, zarządzanie TC, raporty dwupoziomowe, eksporty, WCAG |
| [Billing](billing/01-plany-i-zakup.md) | [plany i zakup](billing/01-plany-i-zakup.md) · [subskrypcja](billing/02-zarzadzanie-subskrypcja.md) · [metody płatności](billing/03-metody-platnosci.md) · [faktury](billing/04-faktury-i-dane-fakturowe.md) · [zużycie i powiadomienia](billing/05-zuzycie-i-powiadomienia.md) · [FAQ](billing/06-faq.md) | plany Freemium/Basic/Premium, tpay, zmiana planu, faktury VAT, limity |
| [Bezpieczeństwo](bezpieczenstwo/01-uruchamianie-skanu.md) | [skan](bezpieczenstwo/01-uruchamianie-skanu.md) · [wyniki](bezpieczenstwo/02-interpretacja-wynikow.md) · [priorytety](bezpieczenstwo/03-priorytetyzacja-napraw.md) · [rekomendacje](bezpieczenstwo/04-rekomendacje-i-patche.md) · [FAQ](bezpieczenstwo/05-faq-bezpieczenstwa.md) | skany SAST/DAST/CVE, interpretacja zagrożeń |
| [Luki funkcjonalne](luki-funkcjonalne/01-uruchamianie-analizy.md) | [analiza](luki-funkcjonalne/01-uruchamianie-analizy.md) · [wyniki](luki-funkcjonalne/02-interpretacja-wynikow.md) · [compliance](luki-funkcjonalne/03-compliance-i-priorytetyzacja.md) · [rekomendacje](luki-funkcjonalne/04-rekomendacje-i-skeleton.md) · [integracje](luki-funkcjonalne/05-integracje-trackery.md) · [FAQ](luki-funkcjonalne/06-faq.md) | porównanie kod↔dokumentacja, compliance, trackery |

## Co gdzie — skrót

- **Kupić plan / zmienić plan / faktura** → [billing](billing/01-plany-i-zakup.md)
- **Wgrać kod/dokumentację, uruchomić analizę** → [interfejs webowy — projekty](interfejs-webowy/02-projekty-i-upload.md)
- **Zinterpretować wyniki skanu bezpieczeństwa** → [bezpieczeństwo](bezpieczenstwo/02-interpretacja-wynikow.md)
- **Znaleźć braki względem dokumentacji** → [luki funkcjonalne](luki-funkcjonalne/01-uruchamianie-analizy.md)

Podręcznik ogólny (części 1–4) jest uzupełnieniem powyższych poradników
modułowych. Wszystkie cztery części są gotowe; zmiany po odbiorze
dokumentacji rejestruje [SIGN-OFF.md](../SIGN-OFF.md).
