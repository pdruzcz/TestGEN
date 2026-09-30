// Golden taint fixture (Story 4.14): servlet parameter flows into a SQL sink.
// Intentionally vulnerable reference sample for taint-analysis regression tests.

public class ProductDao {
    public ResultSet find(HttpServletRequest request, Statement stmt) throws Exception {
        String code = request.getParameter("code"); // source: user_input
        String sql = "SELECT * FROM products WHERE code=" + code; // transform
        return stmt.executeQuery(sql); // sink: sql (sql_injection)
    }
}
