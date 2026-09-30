// Golden SAST sample (JavaScript) — known-vulnerable, Epic 4 Story 4.1.
// Intentionally insecure reference code used to freeze SAST detection output.
// DO NOT use any of this in production. Each flagged line is annotated.

const cp = require("child_process");

function renderProfile(el, userData) {
  // xss (CWE-79) — innerHTML assignment with user data
  el.innerHTML = userData;
}

function runEval(src) {
  // code_injection (CWE-95) — eval on input
  return eval(src);
}

function backup(name) {
  // command_injection (CWE-78) — exec with template interpolation
  cp.exec(`tar -czf ${name}.tar.gz ./data`);
}

const token = "ghp_abcdef0123456789secrettoken"; // hardcoded_secret (CWE-798)

module.exports = { renderProfile, runEval, backup, token };
