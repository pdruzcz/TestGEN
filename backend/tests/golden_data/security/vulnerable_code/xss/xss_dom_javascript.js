// Golden security fixture (Story 4.14) — DOM-based XSS (CWE-79).
// Intentionally vulnerable reference sample for scanner regression tests.

function render(element, userInput) {
  element.innerHTML = userInput;
}
