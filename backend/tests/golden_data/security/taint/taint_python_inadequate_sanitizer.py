# Golden taint sample (Story 4.3): an HTML escaper is applied but the sink is SQL,
# so the sanitizer is inadequate and the flow is still vulnerable.
# Reference fixture — intentionally vulnerable.

import html


def lookup(request, cursor):
    raw = request.GET["id"]        # source: user_input
    safe = html.escape(raw)        # sanitizer (html) — wrong for SQL
    cursor.execute("SELECT * FROM t WHERE id=" + safe)  # sink: sql (still vulnerable)
