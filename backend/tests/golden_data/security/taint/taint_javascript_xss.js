// Golden taint sample (Story 4.3): request data flows into an HTML sink.
// Reference fixture — intentionally vulnerable.

function render(req, element) {
  const name = req.query.name; // source: user_input
  const markup = "<b>" + name + "</b>"; // transform
  element.innerHTML = markup; // sink: html (xss)
}
