# Golden security fixture (Story 4.14) — SQL injection (CWE-89).
# Intentionally vulnerable reference sample for scanner regression tests.


def get_user(cursor, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()
