// Golden security fixture (Story 4.14) — SQL injection (CWE-89).
// Intentionally vulnerable reference sample for scanner regression tests.

public class OrderRepository
{
    public SqlCommand Build(string orderId)
    {
        return new SqlCommand("SELECT * FROM orders WHERE id = " + orderId);
    }
}
