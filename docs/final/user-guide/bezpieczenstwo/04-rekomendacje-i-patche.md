# Przewodnik użytkownika — rekomendacje, patche i PoC

## 1. Rekomendacje naprawcze

```
POST /projects/{project_id}/security-findings/{finding_id}/recommendation
```

`RecommendationEngine` zwraca: opis problemu, opis ryzyka, opis naprawy,
naprawiony snippet kodu i unified diff. Rekomendacje pochodzą z szablonów
(`recommendation_templates/`) per typ podatności i język.

## 2. Patche (git apply)

```
POST /projects/{project_id}/security-findings/{finding_id}/generate-patch
GET  /projects/{project_id}/security-findings/{finding_id}/patch
GET  /projects/{project_id}/security-findings/{finding_id}/patch/preview
GET  /projects/{project_id}/security-findings/{finding_id}/patch/download
```

`PatchGenerator` tworzy unified diff (`diff_generator.py`), waliduje go
względem kodu źródłowego (`is_valid`) i nadaje nazwę
`fix_{typ}_{plik}_{id}.patch`. `preview` pokazuje naprawę bez zapisu.

## 3. Patche zbiorcze i konflikty

```
POST /projects/{project_id}/security-patches/batch
GET  /projects/{project_id}/security-patches/conflicts
```

Wykrywanie konfliktów grupuje znaleziska po pliku i porównuje zakresy linii:
- `critical` — nakładające się linie,
- `warning` — linie sąsiadujące (koniec+1 == początek).

## 4. Proof of Concept (PoC)

```
POST /projects/{project_id}/security-findings/{finding_id}/generate-poc
GET  /projects/{project_id}/security-findings/{finding_id}/poc
```

`PoCGenerator` zwraca: payload, kroki reprodukcji, oczekiwany efekt, flagę
`is_safe` i disclaimer.

## 5. Bezpieczeństwo PoC (poc_safety)

Każdy PoC przechodzi przez `validate_text_safety()`. Blokowane są wzorce
destrukcyjne, m.in.: `DROP TABLE/DATABASE`, `DELETE FROM`, `TRUNCATE`,
`UPDATE ... SET`, `INSERT INTO`, `rm -rf`, `format c:`, `mkfs`,
`shutdown/reboot`, fork bomb, `wget`/`curl -O`, `curl | sh`.

PoC z wykrytym wzorcem destrukcyjnym ma `is_safe = False` i listę
`blocked_reasons` — NIE jest udostępniany do wykonania.

Disclaimer: „PoC służy wyłącznie do weryfikacji podatności. Użycie na
systemach bez autoryzacji jest zabronione.”
