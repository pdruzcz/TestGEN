"""Golden dataset for the self-healing matcher — Story 1.51 (AC: golden test data).

Ten before/after scenarios spanning the locator-strategy space. The aggregate
test enforces accuracy >= 85% and a false-positive rate < 5% (a healthy locator
must never be "healed").
"""

import uuid

import pytest

from app.services.generators.self_healing import (
    GUIElementView,
    NativeMatcher,
    parse_locators,
)


def _el(label, ctype="button", **attrs):
    return GUIElementView(
        component_id=uuid.uuid4(),
        component_type=ctype,
        label=label,
        attributes=attrs,
    )


def _first_loc(code):
    locs = parse_locators(code)
    assert locs, f"no locator parsed from: {code}"
    return locs[0]


# (name, code, elements_a, elements_b, expected: healthy|healed|failed)
GOLDEN = [
    (
        "selenium_id_replaced_by_testid",
        'driver.find_element(By.ID, "username")',
        [_el("Nazwa użytkownika", "input", **{"id": "username"})],
        [_el("Nazwa użytkownika", "input", **{"data-testid": "username-input"})],
        "healed",
    ),
    (
        "selenium_testid_renamed_same_label",
        "driver.find_element(By.CSS_SELECTOR, \"[data-testid='submit-btn']\")",
        [_el("Zaloguj", **{"data-testid": "submit-btn"})],
        [_el("Zaloguj", **{"data-testid": "login-submit"})],
        "healed",
    ),
    (
        "selenium_aria_changed_same_label",
        "driver.find_element(By.CSS_SELECTOR, \"[aria-label='Zamknij']\")",
        [_el("Zamknij", **{"aria-label": "Zamknij"})],
        [_el("Zamknij", **{"aria-label": "Close"})],
        "healed",
    ),
    (
        "playwright_role_unchanged_healthy",
        "page.get_by_role('button', name='Zaloguj')",
        [_el("Zaloguj")],
        [_el("Zaloguj")],
        "healthy",
    ),
    (
        "xpath_element_removed_failed",
        "driver.find_element(By.XPATH, \"//button[@id='gone']\")",
        [_el("X", **{"id": "gone"})],
        [],
        "failed",
    ),
    (
        "selenium_id_unchanged_healthy",
        'driver.find_element(By.ID, "email")',
        [_el("Email", "input", **{"id": "email"})],
        [_el("Email", "input", **{"id": "email"})],
        "healthy",
    ),
    (
        "playwright_id_replaced_by_testid",
        'page.locator("#password")',
        [_el("Hasło", "input", **{"id": "password"})],
        [_el("Hasło", "input", **{"data-testid": "password-field"})],
        "healed",
    ),
    (
        "semantic_rename_testid_and_label_failed",
        "driver.find_element(By.CSS_SELECTOR, \"[data-testid='menu-toggle']\")",
        [_el("Menu", **{"data-testid": "menu-toggle"})],
        [_el("Profil", **{"data-testid": "nav-menu"})],
        "failed",
    ),
    (
        "multi_element_disambiguation_by_label",
        'driver.find_element(By.ID, "save")',
        [_el("Zapisz", **{"id": "save"})],
        [
            _el("Anuluj", **{"data-testid": "cancel"}),
            _el("Zapisz", **{"data-testid": "save-btn"}),
        ],
        "healed",
    ),
    (
        "element_moved_same_label_healed",
        'driver.find_element(By.ID, "search")',
        [_el("Szukaj", "input", **{"id": "search"})],
        [_el("Szukaj", "input", **{"id": "search-moved"})],
        "healed",
    ),
]


def _outcome(code, elements_a, elements_b):
    loc = _first_loc(code)
    if NativeMatcher.target_exists(loc, elements_b):
        return "healthy"
    cand = NativeMatcher.match(loc, elements_a, elements_b)
    if cand is None:
        return "failed"
    return "healed" if cand.confidence >= 0.8 else "needs_review"


@pytest.mark.parametrize(
    ("code", "elements_a", "elements_b", "expected"),
    [(c[1], c[2], c[3], c[4]) for c in GOLDEN],
    ids=[c[0] for c in GOLDEN],
)
def test_golden_case(code, elements_a, elements_b, expected):
    assert _outcome(code, elements_a, elements_b) == expected


def test_golden_accuracy_and_false_positive_rate():
    correct = 0
    healthy_total = 0
    false_positives = 0  # healthy locator marked as healed

    for _name, code, elements_a, elements_b, expected in GOLDEN:
        outcome = _outcome(code, elements_a, elements_b)
        if outcome == expected:
            correct += 1
        if expected == "healthy":
            healthy_total += 1
            if outcome == "healed":
                false_positives += 1

    accuracy = correct / len(GOLDEN)
    fp_rate = false_positives / healthy_total if healthy_total else 0.0

    assert accuracy >= 0.85, f"accuracy {accuracy:.0%} below 85%"
    assert fp_rate < 0.05, f"false-positive rate {fp_rate:.0%} >= 5%"
