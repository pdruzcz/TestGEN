// Golden taint fixture (Story 4.14): request data flows into an HTML sink.
// Intentionally vulnerable reference sample for taint-analysis regression tests.

function render(req, element) {
  const name = req.query.name; // source: user_input
  const markup = "<span>" + name + "</span>"; // transform
  element.innerHTML = markup; // sink: html (xss)
}
