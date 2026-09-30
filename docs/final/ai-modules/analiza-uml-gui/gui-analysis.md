# Analiza GUI — pipeline natywny CV/OCR (Epic 3)

Od screenshotu interfejsu do listy komponentów (`GUIComponent`), drzewa layoutu i
regresji wizualnej. Detekcja czysto heurystyczna (geometria bbox + słowa kluczowe
OCR) — bez modeli ML ani template matchingu. Wszystkie biblioteki obrazowe
(OpenCV, Pillow, pytesseract, EasyOCR, scikit-image, scipy, numpy) są **opcjonalne**
— orchestrator degraduje się łagodnie (wynik częściowy + ostrzeżenia, bez błędu).
Endpointy: [uml_gui_examples.md](../../architecture/api/examples/uml_gui_examples.md); modele:
[uml-gui-data-models.md](./uml-gui-data-models.md).

## Etapy pipeline'u

```
Screenshot GUI (upload, ≤ 20 MB)
  1. Dekodowanie obrazu      (cv2 → Pillow fallback)
  2. OCR                     (Tesseract → EasyOCR fallback, j. pl+en)
  3. Detekcja komponentów    (kontury cv2 + klasyfikacja heurystyczna)
  4. Analiza layoutu         (zagnieżdżanie bbox + przypisanie etykiet)
  → GUIAnalysisOutput (komponenty + bloki OCR + drzewo + ostrzeżenia)
```

## Preprocessing (`component_detector._cv2_regions`)

Skala szarości (`cvtColor`) → rozmycie Gaussa (`GaussianBlur` (3,3)) → krawędzie
(`Canny` 50/150) → dylatacja (jądro 3×3, 2 iter.) → kontury (`findContours`,
`RETR_EXTERNAL`). Dekodowanie: cv2, potem Pillow; brak obu → ostrzeżenie + pusty wynik.

> Uwaga: **brak adaptacyjnego progowania** (thresholding) — pipeline opisany
> wiernie względem kodu.

## OCR (`ocr_service.py`)

- **Tesseract** (główny): `image_to_data(DICT)`, bloki o `confidence ≥ 0.3`.
- **EasyOCR** (fallback): `Reader(["pl","en"], gpu=False)`, gdy Tesseract brak/pusty.
- Brak obu → pusta lista bloków + ostrzeżenie. Blok = `text` + `bbox` + `confidence`.

## Detekcja komponentów (`component_detector.classify_region`)

Kontury → filtr geometrii (szer. ≥ 12, wys. ≥ 8, pow. ≥ 200 px², `confidence ≥ 0.5`)
→ klasyfikacja heurystyczna łączająca aspect ratio/powierzchnię ze słowami kluczowymi OCR.

| Typ (`GUIComponentType`) | Aktywnie wykrywany | Pewność |
|---|---|---|
| `button` | tak | 0.8/0.65 |
| `input` | tak | 0.65 |
| `dropdown` | tak | 0.55 |
| `checkbox` | tak | 0.6 |
| `menu` | tak | 0.7/0.55 |
| `form` | tak | 0.5 |
| `radio`,`link`,`table`,`modal`,`tab` | enum istnieje, brak reguły → zwykle `unknown` | — |
| `unknown` | fallback | 0.3 |

> Odstępstwo od pierwotnego AC (>80% dla 10 typów): aktywnie klasyfikowane 6 z 12
> wartości enuma; pozostałe regiony → `unknown`. Cypress/SikuliX generują kod dla
> każdego poprawnie sklasyfikowanego typu.

## Analiza layoutu (`layout_analyzer.py`)

Zagnieżdżanie przestrzenne wg zawierania bbox: sortowanie po powierzchni (desc) →
najmniejszy zawierający rodzic; nieoznaczone komponenty dostają etykiety OCR z
okolicy (≤ `_LABEL_GAP = 24 px`); korzeń = syntetyczny `screen`. Relacje: zawieranie
button↔form, powiązanie label↔input.

## Regresja wizualna (3.10, `visual_regression.py`)

`POST /projects/{id}/gui/compare` porównuje dwa screenshoty:

- **Różnica pikselowa** (`compute_pixel_diff`): SSIM (scikit-image) → `(1-ssim)*100%`;
  fallback udział pikseli > 30; fallback 0.0 bez numpy.
- **Delta komponentowa** (`compute_component_delta`): `removed`/`added`/`moved` (≤40 px)/
  `layout` (>40 px)/`text` (podobieństwo < 0.85)/`color` (zarezerwowane).
- **Status** (`ComparisonStatus`): `major_diff` (delta BREAKING lub pixel ≥ 30%) /
  `match` (pixel < 2% i brak delt) / `minor_diff` / `error`.
- **Dopasowanie** (`match_components`): `0.4*IoU + 0.3*etykiety + 0.3*typ`;
  algorytm węgierski (scipy) lub zachłanny; próg 0.6.

## Generowanie PNG SikuliX (domknięcie 3-13)

SikuliX jest image-based — skrypt referuje `Pattern("images/...")`. Dedykowany
pipeline `sikulix_pipeline.generate_sikulix_code` (oddzielony od ścieżki Cypress,
bo wymaga obrazów):

1. **Linkage step→GUIComponent** (`resolve_step_component`): explicit `step.component`
   z bbox → `component_id` (lookup) → label-match (`target`/`target_element` ↔
   `GUIComponent.label`, diakrytyki/whitespace → `_`). Brak → krok bez patternu.
2. **Crop**: komponenty pogrupowane po `storage_key` → pobranie screenshotu raz
   z MinIO → `PatternCropper.crop_all_components` (bbox→PNG, Pillow).
3. **Persystencja**: PNG wgrywane do MinIO (`{tenant}/{project}/sikuli/{test_case_id}/images/{name}`)
   i odnotowane w `TestCode.pattern_images` JSONB (`[{name, storage_key, component_id}]`).
   Nazwa PNG (`{ctype}_{label}.png`) spójna między cropperem a generatorem → skrypt
   referuje realnie wyprodukowane pliki.
4. **Graceful degrade**: bez Pillow → `crop_all_components` zwraca `[]` + warning →
   skrypt ze statycznymi referencjami, `pattern_images = null` (nie crash).

Patrz [ADR-012](../../architecture/adr/ADR-012-sikulix-image-based.md).

## Moduł → serwis → story

| Komponent | Serwis | Story |
|---|---|---|
| upload screenshotu | `GUIUploadService` | 3.8 |
| analiza CV/OCR | `gui/orchestrator.py` | 3.8 |
| flows z sekwencji ekranów | `gui/flow_service.py` | 3.9 |
| regresja wizualna | `visual_regression.py` | 3.10 |
| PNG SikuliX | `sikulix_pipeline.py`, `pattern_cropper.py` | 3.13, 3-13 |

## Ograniczenia

- Detekcja heurystyczna wrażliwa na motyw (jasny/ciemny), font, DPI, nakładające
  się elementy — brak ML/template matchingu.
- Brak twardej walidacji min. rozdzielczości (rozmiar zapisywany, nie odrzucany);
  formaty szersze niż pierwotne AC (dodatkowo BMP/TIFF).
- Jakość OCR zależy od kontrastu i obecności Tesseract/EasyOCR w środowisku.

## Powiązane

- [uml-parsing.md](./uml-parsing.md) — osobny pipeline diagramów UML.
- [test-generation-uml-gui.md](./test-generation-uml-gui.md) — flows → Gherkin → kod.
- [ADR-012](../../architecture/adr/ADR-012-sikulix-image-based.md), [ADR-008](../../architecture/adr/ADR-008-golden-data.md).
