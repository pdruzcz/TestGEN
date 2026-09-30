# Golden security fixture (Story 4.14) — hardcoded password (CWE-798).
# Intentionally vulnerable reference sample for scanner regression tests.

DB_PASSWORD = "Sup3rS3cr3tP@ss"


def connect():
    return open_connection(user="admin", password=DB_PASSWORD)
