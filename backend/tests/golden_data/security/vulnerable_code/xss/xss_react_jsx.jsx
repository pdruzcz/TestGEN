// Golden security fixture (Story 4.14) — React XSS via raw HTML (CWE-79).
// Intentionally vulnerable reference sample for scanner regression tests.

export function Comment({ data }) {
  return <div dangerouslySetInnerHTML={{ __html: data }} />;
}
