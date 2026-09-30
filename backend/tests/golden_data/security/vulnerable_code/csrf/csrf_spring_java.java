// Golden security fixture (Story 4.14) — CSRF disabled in Spring Security (CWE-352).
// Intentionally vulnerable reference sample for scanner regression tests.

public class SecurityConfig {
    protected void configure(HttpSecurity http) throws Exception {
        http.csrf().disable().authorizeRequests().anyRequest().authenticated();
    }
}
