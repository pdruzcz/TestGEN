# Golden taint fixture (Story 4.14): request input flows into a SQL sink.
# Intentionally vulnerable reference sample for taint-analysis regression tests.


def lookup(request, cursor):
    user_id = request.GET["id"]                         # source: user_input
    query = "SELECT * FROM accounts WHERE id=" + user_id  # transform
    cursor.execute(query)                                # sink: sql (sql_injection)
    return cursor.fetchone()
