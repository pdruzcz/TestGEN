// Golden security fixture (Story 4.14) — CSRF middleware disabled (CWE-352).
// Intentionally vulnerable reference sample for scanner regression tests.

const session = require("cookie-session");

app.use(session({ csrf: false, secret: loadSecret() }));
