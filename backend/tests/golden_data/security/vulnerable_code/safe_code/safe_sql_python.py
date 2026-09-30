# Golden safe fixture (Story 4.14): parameterized query — must NOT be flagged.
# False-positive guard for the SAST regression suite.


def get_user(cursor, user_id):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone()
