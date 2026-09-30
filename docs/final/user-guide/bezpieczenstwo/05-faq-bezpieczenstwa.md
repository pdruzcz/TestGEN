# Przewodnik użytkownika — FAQ bezpieczeństwa

## Pytania ogólne

**P: Czy wyniki skanu są powtarzalne?**
O: Tak. Silniki są deterministyczne (reguły i analiza przepływu danych) —
te same dane wejściowe dają ten sam wynik, bez zależności od usług
zewnętrznych.

**P: Czy skan wymaga dostępu do internetu?**
O: SAST, TAINT, CONFIG i DEPENDENCY (z lokalną bazą CVE) działają offline. DAST
wymaga uruchomionej aplikacji do testowania.

**P: Skąd biorą się dane CVE?**
O: Z NVD, OSV.dev i GitHub Advisory, synchronizowanych miesięcznie do lokalnej
tabeli `cve_database` (patrz [źródła danych](../../ai-modules/bezpieczenstwo/04-pipeline-cve/01-zrodla-danych.md)).

## Jakość wyników

**P: Mam false positive — co zrobić?**
O: Ustaw status znaleziska na `FALSE_POSITIVE`
(`PATCH .../security-findings/{id}/status`). Reguły są strojone tak, by
utrzymać FP < 30% na korpusie golden (Story 4.14).

**P: Dlaczego to samo znalezisko ma różny confidence?**
O: Confidence zależy od narzędzia i potwierdzeń. Znalezisko wykryte przez wiele
narzędzi lub potwierdzone dynamicznie (SAST↔DAST) ma wyższy confidence.

**P: Co oznacza eskalacja severity?**
O: Risk engine podnosi severity, gdy podatność jest potwierdzona dynamicznie
lub dotyczy zależności z publicznym exploitem (CVSS ≥ 9.0). Powód w
`escalation_reason`.

## Naprawy

**P: Czy mogę zastosować patch automatycznie?**
O: Patch to unified diff walidowany względem kodu (`is_valid`). Pobierz przez
`/patch/download` i zastosuj `git apply`. Przy wielu naprawach w jednym pliku
sprawdź konflikty (`/security-patches/conflicts`).

**P: Czy PoC jest bezpieczny do uruchomienia?**
O: PoC przechodzi przez filtr `poc_safety` blokujący operacje destrukcyjne. PoC
z `is_safe=False` nie jest udostępniany. Uruchamiaj wyłącznie na autoryzowanych
systemach.

## Troubleshooting

**P: Skan ma status FAILED.**
O: Sprawdź `error_message` w statusie skanu. Dla DAST najczęstsze przyczyny to
niedostępny `target_url` lub timeout (limit 30 min).

**P: Skan DAST nie pokrywa chronionych ścieżek.**
O: Podaj `auth_config` (form/token/basic), aby skaner działał jako
uwierzytelniony użytkownik.

**P: Aktualizacja CVE nie zadziałała.**
O: Sprawdź `CVEUpdateLog` i `SourceStatus` per źródło. Zadanie ma 3 retry z
backoffem; błąd jednego źródła nie przerywa całego przebiegu.
