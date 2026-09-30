// Golden security fixture (Story 4.14) — SQL injection (CWE-89).
// Intentionally vulnerable reference sample for scanner regression tests.

function getProduct(db, req) {
  return db.query("SELECT * FROM products WHERE id = " + req.params.id);
}
