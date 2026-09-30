// Golden taint sample (Story 4.3): servlet parameter flows into a SQL sink.
// Reference fixture — intentionally vulnerable.

public class UserDao {
    public ResultSet find(HttpServletRequest request, Statement stmt) throws Exception {
        String id = request.getParameter("id"); // source: user_input
        String sql = "SELECT * FROM users WHERE id=" + id; // transform
        return stmt.executeQuery(sql); // sink: sql (sql_injection)
    }
}
