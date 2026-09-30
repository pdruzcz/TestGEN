// Golden security fixture (Story 4.14) — SQL injection (CWE-89).
// Intentionally vulnerable reference sample for scanner regression tests.

public class UserDao {
    public ResultSet findByName(Statement stmt, String name) throws Exception {
        return stmt.executeQuery("SELECT * FROM users WHERE name = '" + name + "'");
    }
}
