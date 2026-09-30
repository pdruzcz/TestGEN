// Golden security fixture (Story 4.14) — hardcoded AWS access key (CWE-798).
// Intentionally vulnerable reference sample for scanner regression tests.

public class AwsConfig {
    public static final String ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE";
}
