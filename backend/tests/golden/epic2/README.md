# Epic 2 Golden Test Data

Golden test data for Epic 2: "Analiza dokumentacji i detekcja rozbieżności".

## Purpose

This directory contains expected outputs for testing all Epic 2 features. These golden data files serve as:

1. **Reference outputs** for validating implementation correctness
2. **Regression testing** baseline for future changes
3. **Documentation** of expected behavior for each feature

## Files Overview

| File | Feature | Story | Description |
|------|---------|-------|-------------|
| `sample_document.json` | Input fixture | - | Sample Polish technical specification document |
| `expected_preprocessing.json` | Preprocessing | 2.2 | Expected document structure and cleaned sections |
| `expected_classification.json` | Classification | 2.3 | Expected document type, domain, and confidence scores |
| `expected_requirement_extraction.json` | Requirements | 2.4 | Expected extracted requirements with metadata |
| `expected_glossary_extraction.json` | Glossary | 2.6 | Expected terms, definitions, and code suggestions |
| `expected_inconsistency_detection.json` | Inconsistencies | 2.7 | Expected detected issues and severity levels |
| `expected_gap_analysis.json` | Gap Analysis | 2.8 | Expected coverage status and missing implementations |
| `expected_traceability_matrix.json` | Traceability | 2.9 | Expected requirement-to-code/test mappings |
| `expected_test_generation.json` | Test Generation | 2.10 | Expected generated test cases with steps |

## Usage in Tests

```python
from app.services.golden_data import GoldenDataManager, GoldenDataSet, GoldenDataType

# Load golden data
manager = GoldenDataManager("backend/tests/golden/epic2")
golden = manager.load_golden_data("epic2_expected_requirement_extraction", "1.0")

# Compare with actual output
result = manager.compare_with_golden(
    actual=requirement_extractor.extract(document),
    golden_name="epic2_expected_requirement_extraction",
    version="1.0"
)

assert result["status"] == "pass"
```

## Document Structure

The sample document (`sample_document.json`) represents a Polish technical specification for an Order Management System (System Zarządzania Zamówieniami - SZZ) with:

- **8 requirements** (4 functional, 4 non-functional)
- **Glossary section** with 5 defined terms
- **Hierarchical structure** (3 levels of sections)
- **Polish language** content
- **Common requirement patterns** (login, CRUD, performance, security)

## Coverage

Golden data covers the following Epic 2 stories:

- ✅ Story 2.2: Preprocessing dokumentów
- ✅ Story 2.3: Klasyfikacja dokumentów
- ✅ Story 2.4: Ekstrakcja wymagań (native)
- ✅ Story 2.5: Ekstrakcja wymagań (LLM)
- ✅ Story 2.6: Słownik terminów
- ✅ Story 2.7: Detekcja niespójności
- ✅ Story 2.8: Analiza różnic dokument-kod
- ✅ Story 2.9: Macierz traceability
- ✅ Story 2.10: Generowanie testów

## Versioning

All golden data files follow semantic versioning (1.0, 1.1, etc.). When updating golden data:

1. Update the version number
2. Document the change in `metadata.updated_reason`
3. Keep previous versions for regression testing

## Contributing

When adding new features that modify expected outputs:

1. Run the feature against `sample_document.json`
2. Capture the actual output
3. Review and validate the output
4. Save as new golden data file
5. Update this README

## Test Data

The sample document contains realistic test scenarios:

| Aspect | Details |
|--------|---------|
| Language | Polish (pl) |
| Domain | E-commerce / Order Management |
| Document Type | SRS (Software Requirements Specification) |
| Requirements | 8 total (4 FR, 4 NFR) |
| Glossary Terms | 5 terms (SZZ, Zamówienie, RBAC, TLS, API) |
| Complexity | Medium (hierarchical with tables) |
| Standards | IEEE-830 |

## Inconsistencies Included

The golden data intentionally includes common document issues for validation:

1. **Terminology inconsistency**: "Zamówienie" has multiple variants
2. **Missing reference**: Status "W trakcie realizacji" is referenced but not defined

These serve as positive tests for the inconsistency detector (Story 2.7).
