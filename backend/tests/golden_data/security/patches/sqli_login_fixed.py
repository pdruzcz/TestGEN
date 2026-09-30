"""Golden sample (Story 4.11) — test fixture, not production code."""


def authenticate(cursor, username):
    query = "SELECT * FROM users WHERE username = %s"
    cursor.execute(query, (username,))
    return cursor.fetchone()
