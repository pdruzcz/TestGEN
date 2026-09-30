# Motywy dostępności — wysoki kontrast i redukcja animacji

> Dokumentacja P2, Epic 6 — Story 6-10.
> Implementacja: `shared/services/theme.service.ts`,
> `shared/components/accessibility-toolbar/`,
> `shared/styles/themes/_high-contrast.scss`, `_motion.scss`,
> dyrektywa `reduced-motion.directive.ts`.

## 1. Mechanizm

Motywy to klasy CSS na `<body>` sterowane sygnałami `ThemeService`:

| Motyw | Klasa na `<body>` | Signal | Klucz localStorage |
|---|---|---|---|
| Wysoki kontrast | `high-contrast` | `isHighContrastSignal` | `testgen:a11y:high-contrast` |
| Redukcja animacji | `reduced-motion` | `isReducedMotionSignal` | `testgen:a11y:reduced-motion` |

**Priorytet preferencji**: jawny wybór użytkownika (localStorage) >
preferencje systemowe (`prefers-contrast: more`,
`prefers-reduced-motion: reduce`) > wyłączone. Zmiana preferencji
systemowej w trakcie sesji jest śledzona (`matchMedia … change`) i
stosowana, dopóki użytkownik nie dokonał jawnego wyboru. localStorage
niedostępny (tryb prywatny) — preferencja żyje w pamięci sesji.

## 2. Pasek dostępności (toolbar)

`accessibility-toolbar.component` — montowany w korzeniu aplikacji,
widoczny na **każdej stronie**: rozwijalny pasek z dwoma przełącznikami
(wysoki kontrast, wyłączenie animacji). Stan przełączników odzwierciedla
sygnały; kliknięcie zapisuje preferencję trwale.

## 3. Tryb wysokiego kontrastu

Motyw `themes/_high-contrast.scss` — paleta czarno-biała z akcentami,
kontrast liczony na białym tle:

| Element | Kolor | Kontrast |
|---|---|---|
| Tekst | `#000000` | 21:1 |
| Linki/akcje | `#001a99` | 14,3:1 |
| Błędy | `#740006` | 12,4:1 |
| Sukces | `#0d3d1c` | 12,7:1 |
| Ostrzeżenia | `#4d2e00` | 11,7:1 |
| Nieaktywne | `#595959` | 7:1 |

Progi motywu: tekst ≥ **7:1** (poziom AAA), elementy UI ≥ **4,5:1** —
 celowo ostrzejsze niż minimum AA, by tryb miał zapas po nałożeniu się
 komponentów Material. Motyw nadpisuje też stany Material (form fields,
 przyciski, tabele) i wymusza pełne obramowania tam, gdzie kolor był
 jedynym wyróżnikiem.

## 4. Redukcja animacji

- `body.reduced-motion` wyłącza animacje przejść/transformat globalnie
  (`_motion.scss` + arkusz motywu),
- `reduced-motion.directive` stosowana w komponentach z własnymi
  animacjami (progress, wykresy) — animacja zamieniana na zmianę stanu,
- wejściowa detekcja systemowa (`prefers-reduced-motion`) działa także
  bez interakcji użytkownika.

## 5. Zoom i responsywność

Layout aplikacji pracuje do **200% zoomu** i **320 px** szerokości bez
utraty treści i funkcji (reflow 1.4.10): siatki płynne, tabele z
przewijaniem poziomym w kontenerze (nigdy cała strona), breakpointy w
`_responsive.scss`.
