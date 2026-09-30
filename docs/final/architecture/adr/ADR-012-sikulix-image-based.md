# ADR-012: SikuliX image-based — dedykowany pipeline PNG + `pattern_images`

## Status

Accepted

## Kontekst

SikuliX jest frameworkiem image-based — wygenerowany skrypt referuje elementy
przez `Pattern("images/...")`. `PatternCropper` (`crop_element`/`crop_all_components`,
Pillow) istniał jako gotowe, przetestowane narzędzie, ale task Celery
`_generate_sikulix_code_impl` wołał jedynie generyczne `generate_code_for_test_cases`,
ignorując `PatternCropper`. Efekt: skrypt referował `Pattern("images/...")` do plików
PNG, które **nigdy nie powstawały** — AC-2 Story 3.13 (bbox crop → PNG patterns)
było niespięte w ścieżce generowania.

Brakowało też linkage'u `TestStep`↔`GUIComponent` (który komponent/bbox/label
należy do którego kroku testu).

## Decyzja

**Osobny pipeline** `sikulix_pipeline.generate_sikulix_code` (domknięcie 3-13),
oddzielony od generycznej ścieżki Cypress — SikuliX wymaga obrazów, więc separacja
jest uzasadniona warstwowo. Pipeline:

1. **Linkage step→GUIComponent** (`resolve_step_component`): explicit `step.component`
   z bbox → `component_id` (lookup) → label-match (`target`/`target_element` ↔
   `GUIComponent.label`, diakrytyki/whitespace → `_`); brak → krok bez patternu.
2. **Crop**: komponenty pogrupowane po `storage_key` → pobranie screenshotu raz z
   MinIO → `PatternCropper.crop_all_components` → PNG.
3. **Persystencja**: PNG do MinIO (`{tenant}/{project}/sikuli/{test_case_id}/images/{name}`)
   + nowa kolumna `TestCode.pattern_images` JSONB (`[{name, storage_key, component_id}]`,
   migracja `026`). Nazwa PNG spójna między cropperem a generatorem.
4. **Graceful degrade**: bez Pillow → `[]` + warning → skrypt ze statycznymi
   referencjami, `pattern_images = null` (nie crash).

## Konsekwencje

**Pozytywne:**

- Skrypty SikuliX referują realnie wyprodukowane PNG — są uruchamialne.
- `pattern_images` daje mapowanie TestCode→patterny w MinIO (odwraca decision z
  oryginalnego 3.13 „brak kolumny" — bez niej patterny byłyby osierocone).

**Negatywne:**

- Dwa codegen-pipeline'y (Cypress + SikuliX) zamiast jednego generycznego —
  uzasadnione różnicą DOM vs image.
- Zależność od Pillow (opcjonalna, image-gated).

## Powiązane

- [ai/gui-analysis.md](../../ai-modules/analiza-uml-gui/gui-analysis.md) — pipeline PNG + `pattern_images`.
- [ai/test-generation-uml-gui.md](../../ai-modules/analiza-uml-gui/test-generation-uml-gui.md) — codegen.
- [ADR-007](./ADR-007-e2e-frameworks.md) — frameworki E2E.
- Domknięcie `3-13` (`_bmad-output/implementation-artifacts/E3/3-13-domkniecie.md`).
