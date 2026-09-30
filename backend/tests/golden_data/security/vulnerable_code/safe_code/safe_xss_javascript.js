// Golden safe fixture (Story 4.14): textContent escapes output — must NOT be flagged.
// False-positive guard for the SAST regression suite.

function render(element, userInput) {
  element.textContent = userInput;
}
