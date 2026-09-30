// Golden security fixture (Story 4.14) — command injection (CWE-78).
// Intentionally vulnerable reference sample for scanner regression tests.

const child_process = require("child_process");

function listDir(dir) {
  child_process.exec("ls -la " + dir);
}
