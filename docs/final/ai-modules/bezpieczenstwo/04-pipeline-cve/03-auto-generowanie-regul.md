# Pipeline CVE — auto-generowanie reguł SAST

## 1. Cel

Dla wybranych nowych rekordów CVE pipeline może wygenerować szkic reguły
SAST (regex + typ + CWE), aby wykrywać podatny wzorzec bezpośrednio w
kodzie — uzupełnienie detekcji opartej na wersji pakietu.

## 2. Generowanie

```python
async def _generate_sast_rules(records) -> list[VulnerabilityRule]
```

Na podstawie opisu CVE powstaje szkic reguły z polami `REGEX:` / `TYPE:` /
`CWE:` (`module="security"`, `task_type="cve_rule_generation"`).

## 3. Parsowanie szkicu

```python
def _parse_rule_response(text, rec) -> VulnerabilityRule | None
```

Ekstrahuje pola `REGEX:`/`TYPE:`/`CWE:` i tworzy `VulnerabilityRule`
z `confidence_weight=0.3` (niższe zaufanie niż reguły ręczne — szkic
wymaga potwierdzenia w praktyce).

## 4. Walidacja na golden data

```python
def _validate_rule_on_golden_data(rule, safe_samples) -> RuleValidation
```

- Oblicza FPR (false-positive rate) na próbkach bezpiecznych.
- Próg: `_MAX_FPR = 0.05` (5%).
- `RuleValidation` — `rule_id`, `fpr`, `passed`, `sample_size`.

Reguła, która generuje zbyt wiele fałszywych alarmów (FPR ≥ 5%), nie przechodzi
walidacji i nie jest włączana. Powiązanie z korpusem golden:
[golden test data](../../../../../backend/tests/golden_data/security/).

## 5. Bezpieczeństwo procesu

Auto-generowanie jest bramkowane walidacją FPR na golden data, co chroni
przed degradacją jakości detekcji przy cichym dodawaniu reguł. To uzupełnia
regresyjną suitę progową ze Story 4.14.
