# Golden taint sample (Story 4.3): user input flows into a SQL sink unsanitized.
# Reference fixture for taint-analysis regression tests — intentionally vulnerable.


def get_user(request, cursor):
    user_id = request.GET["id"]            # source: user_input
    query = "SELECT * FROM users WHERE id=" + user_id  # transform
    cursor.execute(query)                  # sink: sql (sql_injection)
    return cursor.fetchone()
