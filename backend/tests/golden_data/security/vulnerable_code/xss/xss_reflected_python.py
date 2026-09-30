# Golden security fixture (Story 4.14) — reflected XSS (CWE-79).
# Intentionally vulnerable reference sample for scanner regression tests.

from flask import render_template_string


def greet(user_input):
    return render_template_string(f"<h1>Witaj {user_input}</h1>")
