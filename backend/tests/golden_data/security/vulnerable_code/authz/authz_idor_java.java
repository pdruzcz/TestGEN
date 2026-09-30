// Golden security fixture (Story 4.14) — IDOR (CWE-639).
// Intentionally vulnerable reference sample for scanner regression tests.

public class AccountController {
    public Account getAccount(@PathVariable Long id) {
        return accountRepository.findById(id);
    }
}
