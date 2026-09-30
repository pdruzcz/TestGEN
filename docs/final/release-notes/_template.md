# Szablon release notes

> Skopiuj sekcję poniżej na początek [release-notes.md](release-notes.md)
> (najnowsza wersja na górze) i uzupełnij. Równolegle dopisz wpis do
> [CHANGELOG.md](CHANGELOG.md) — release notes są dla ludzi, changelog dla
> tych, którzy aktualizują instalację.

## Jak wypełniać

- **Podsumowanie** — jedno, dwa zdania dla kogoś, kto nie przeczyta reszty:
  co najważniejszego się zmieniło i kogo to dotyczy.
- **Nowe funkcje** — każda z epikiem i story, żeby dało się dojść do
  szczegółów w `_bmad-output/implementation-artifacts/`.
- **Ulepszenia** i **Poprawki błędów** — opisuj skutek dla użytkownika,
  nie zmianę w kodzie („raport PDF generuje się bez przekroczenia czasu",
  nie „zwiększono timeout workera").
- **Znane problemy** — zawsze z obejściem; problem bez obejścia to powód,
  żeby wstrzymać wydanie.
- **Breaking changes** i **Wymagania migracji** — sekcje obowiązkowe; gdy
  nic się nie łamie, wpisz „brak", żeby było widać, że ktoś to sprawdził.
- Sekcje bez treści zostawiaj z „brak" zamiast je usuwać — czytelnik
  porównujący wersje szuka ich w tym samym miejscu.

## Szablon

```markdown
## vX.Y — Faza PZ (QN RRRR)

**Data wydania:** [miesiąc rok] · **Faza:** [numer — opis]

### Podsumowanie

[1–2 zdania opisujące najważniejsze zmiany]

### Nowe funkcje

| Funkcja | Epik | Opis |
|---------|------|------|
| ... | ... | ... |

### Ulepszenia

- [opis ulepszenia]

### Poprawki błędów

- [opis poprawki]

### Znane problemy

| Problem | Obejście |
|---------|----------|
| ... | ... |

### Breaking changes

- [opis zmiany łamiącej kompatybilność albo „brak"]

### Wymagania migracji

1. [krok migracji albo „brak"]
```

---

[↩ Release notes](release-notes.md) · [Changelog](CHANGELOG.md)
