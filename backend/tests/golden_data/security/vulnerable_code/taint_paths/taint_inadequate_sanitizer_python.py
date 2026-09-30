# Golden taint fixture (Story 4.14): an HTML escaper is applied but the sink is
# SQL, so the sanitizer is inadequate and the flow remains vulnerable.
# Intentionally vulnerable reference sample for taint-analysis regression tests.

import html


def search(request, cursor):
    term = request.GET["q"]                 # source: user_input
    safe = html.escape(term)                # sanitizer (html) — wrong for SQL
    cursor.execute("SELECT * FROM docs WHERE title=" + safe)  # sink: sql
