# **7.3.** Bezpieczeństwo

### **7.3.1.** Uwierzytelnianie i autoryzacja

**REQ-SEC-001:** System musi wykorzystywać OAuth 2.0 / OpenID Connect do
uwierzytelniania użytkowników.

**REQ-SEC-002:** Hasła muszą być hashowane z wykorzystaniem bcrypt lub
Argon2 (minimum 12 rounds).

**REQ-SEC-003:** System musi wspierać Multi-Factor Authentication (MFA)
poprzez TOTP lub SMS.

**REQ-SEC-004:** Tokeny JWT muszą wygasać po maksymalnie 1 godzinie, z
możliwością odświeżenia poprzez refresh token (ważny do 7 dni).

### **7.3.2.** Szyfrowanie danych

**REQ-SEC-005:** Wszystkie połączenia muszą wykorzystywać TLS 1.3
(minimum TLS 1.2).

**REQ-SEC-006:** Dane wrażliwe w bazie danych muszą być szyfrowane w
spoczynku (encryption at rest) z wykorzystaniem AES-256.

**REQ-SEC-007:** Kod źródłowy przesłany przez użytkowników musi być
szyfrowany podczas przechowywania.

### **7.3.3.** Bezpieczeństwo API

**REQ-SEC-008:** System musi implementować rate limiting: 100
requests/minute dla użytkownika Basic, 1000 requests/minute dla
Professional.

**REQ-SEC-009:** API musi być zabezpieczone przed atakami OWASP Top 10
(SQL Injection, XSS, CSRF, etc.).

**REQ-SEC-010:** System musi implementować CORS policy z whitelistą
dozwolonych origin.

### **7.3.4.** Audyt i monitoring bezpieczeństwa

**REQ-SEC-011:** Wszystkie operacje wrażliwe muszą być logowane (audit
log): logowanie, zmiana hasła, dostęp do danych, zmiany
uprawnień.

**REQ-SEC-012:** System musi przechowywać logi audytowe przez minimum 1
rok.

**REQ-SEC-013:** System musi alertować administratorów o podejrzanych
aktywnościach (brute force, unauthorized access attempts).

### **7.3.5.** Zgodność z regulacjami

+---------------+-----------------------------------+--------------------+
| **Regulacja** | **Wymagania**                     | **Status           |
|               |                                   | implementacji**    |
+===============+===================================+====================+
| RODO/GDPR     | - Prawo do usunięcia danych       | Wymagane           |
|               |                                   |                    |
|               | - Prawo do przenoszenia danych    |                    |
|               |                                   |                    |
|               | - Zgoda na przetwarzanie          |                    |
|               |                                   |                    |
|               | - Data breach notification (72h)  |                    |
+---------------+-----------------------------------+--------------------+
| SOC 2 Type II | - Security controls               | Planowane (rok 2)  |
|               |                                   |                    |
|               | - Availability guarantees         |                    |
|               |                                   |                    |
|               | - Confidentiality measures        |                    |
+---------------+-----------------------------------+--------------------+
| ISO 27001     | - ISMS implementation             | Planowane (rok 2)  |
|               |                                   |                    |
|               | - Risk management                 |                    |
|               |                                   |                    |
|               | - Security policies               |                    |
+---------------+-----------------------------------+--------------------+
