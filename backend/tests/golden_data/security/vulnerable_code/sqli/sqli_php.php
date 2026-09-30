<?php
// Golden security fixture (Story 4.14) — SQL injection (CWE-89).
// Intentionally vulnerable reference sample for scanner regression tests.

function get_user($conn, $userId) {
    return mysqli_query($conn, "SELECT * FROM users WHERE id = ${userId}");
}
