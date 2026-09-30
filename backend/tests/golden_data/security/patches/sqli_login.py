"""Golden sample (Story 4.11) — test fixture, not production code."""


def authenticate(cursor, username):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()
