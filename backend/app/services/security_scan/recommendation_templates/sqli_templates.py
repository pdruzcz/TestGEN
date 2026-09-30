"""SQL injection remediation templates — Epic 4, Story 4.9.

Parameterised-query fixes per language / ORM. Importing this module registers
every template in the shared registry.
"""

from app.services.security_scan.recommendation_templates.registry import Template, register

_VULN = "sql_injection"

_PROBLEM = (
    "Zapytanie SQL jest budowane przez konkatenację danych wejściowych użytkownika. "
    "Pozwala to atakującemu wstrzyknąć własny kod SQL i zmienić logikę zapytania."
)
_RISK = (
    "Atakujący może odczytać, zmodyfikować lub usunąć dowolne dane z bazy, "
    "ominąć uwierzytelnianie, a w skrajnym przypadku przejąć serwer bazy danych."
)
_FIX = "Użyj zapytań parametryzowanych (prepared statements) zamiast konkatenacji ciągów znaków."


register(
    _VULN,
    "python",
    "django",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Django ORM przekazuj parametry jako listę.",
        fixed_code_snippet='cursor.execute("SELECT * FROM users WHERE id = %s", [user_id])',
        language="python",
        framework="django",
    ),
)

register(
    _VULN,
    "python",
    "sqlalchemy",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W SQLAlchemy korzystaj z wyrażeń ORM/bindparam.",
        fixed_code_snippet="session.query(User).filter(User.id == user_id).all()",
        language="python",
        framework="sqlalchemy",
    ),
)

register(
    _VULN,
    "python",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Pythonie przekazuj parametry jako krotkę do execute().",
        fixed_code_snippet='cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
        language="python",
    ),
)

register(
    _VULN,
    "java",
    "jdbc",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W JDBC użyj PreparedStatement z placeholderami '?'.",
        fixed_code_snippet=(
            'PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");\n'
            "ps.setInt(1, userId);\n"
            "ResultSet rs = ps.executeQuery();"
        ),
        language="java",
        framework="jdbc",
    ),
)

register(
    _VULN,
    "java",
    "spring",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Spring Data użyj parametrów nazwanych w @Query.",
        fixed_code_snippet=(
            '@Query("SELECT u FROM User u WHERE u.id = :id")\n'
            "User findById(@Param(\"id\") Long id);"
        ),
        language="java",
        framework="spring",
    ),
)

register(
    _VULN,
    "java",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Javie zawsze używaj PreparedStatement.",
        fixed_code_snippet=(
            'PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");\n'
            "ps.setInt(1, userId);"
        ),
        language="java",
    ),
)

register(
    _VULN,
    "javascript",
    "node",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Node przekazuj parametry jako tablicę do query().",
        fixed_code_snippet='pool.query("SELECT * FROM users WHERE id = ?", [userId]);',
        language="javascript",
        framework="node",
    ),
)

register(
    _VULN,
    "javascript",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W JavaScript używaj zapytań parametryzowanych sterownika bazy.",
        fixed_code_snippet='db.query("SELECT * FROM users WHERE id = $1", [userId]);',
        language="javascript",
    ),
)

register(
    _VULN,
    "csharp",
    "ef",
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W Entity Framework korzystaj z LINQ zamiast surowego SQL.",
        fixed_code_snippet="context.Users.Where(u => u.Id == id).ToList();",
        language="csharp",
        framework="ef",
    ),
)

register(
    _VULN,
    "csharp",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX + " W ADO.NET użyj SqlParameter.",
        fixed_code_snippet=(
            'var cmd = new SqlCommand("SELECT * FROM Users WHERE Id = @id", conn);\n'
            'cmd.Parameters.AddWithValue("@id", id);'
        ),
        language="csharp",
    ),
)

register(
    _VULN,
    "generic",
    None,
    Template(
        problem_description=_PROBLEM,
        risk_description=_RISK,
        fix_description=_FIX,
        fixed_code_snippet='query("SELECT * FROM users WHERE id = ?", [user_id])',
        language="generic",
    ),
)
