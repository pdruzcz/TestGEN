# **10.2.** Przykłady kodów źródłowych

### **10.2.1.** Przykład 1: Kod z podatnością SQL Injection

**Kod podatny (Python):**

import sqlite3 def get_user(username): conn =
sqlite3.connect(\'users.db\') cursor = conn.cursor() \# PODATNOŚĆ: SQL
Injection query = f\"SELECT \* FROM users WHERE username =
\'{username}\'\" cursor.execute(query) user = cursor.fetchone()
conn.close() return user \# Atak: get_user(\"admin\' OR \'1\'=\'1\") \#
Zwróci wszystkich użytkowników!

**Kod bezpieczny (Python):**

import sqlite3 def get_user(username): conn =
sqlite3.connect(\'users.db\') cursor = conn.cursor() \# BEZPIECZNE:
Parametryzowane zapytanie query = \"SELECT \* FROM users WHERE username
= ?\" cursor.execute(query, (username,)) user = cursor.fetchone()
conn.close() return user

**Testy wygenerowane przez TestGEN:**

import pytest from app import get_user def
test_sql_injection_protection(): \"\"\"Test that SQL injection attempts
are prevented\"\"\" \# Próba ataku SQL injection malicious_input =
\"admin\' OR \'1\'=\'1\" result = get_user(malicious_input) \# Powinno
zwrócić None (brak użytkownika) zamiast wszystkich użytkowników assert
result is None, \"SQL injection vulnerability detected!\" def
test_get_user_valid(): \"\"\"Test getting user with valid username\"\"\"
result = get_user(\"john_doe\") assert result is not None assert
result\[1\] == \"john_doe\" \# username column def
test_get_user_invalid(): \"\"\"Test getting user with non-existent
username\"\"\" result = get_user(\"nonexistent_user_12345\") assert
result is None

### **10.2.2.** Przykład 2: Kod z podatnością XSS

**Kod podatny (JavaScript/React):**

function UserComment({ comment }) { // PODATNOŚĆ: XSS -
dangerouslySetInnerHTML return (

); } // Atak: comment.text = \"\"

**Kod bezpieczny (JavaScript/React):**

import DOMPurify from \'dompurify\'; function UserComment({ comment }) {
// BEZPIECZNE: Sanityzacja HTML const sanitizedText =
DOMPurify.sanitize(comment.text); return (

); } // Lub jeszcze lepiej - bez innerHTML: function UserCommentSafe({
comment }) { return (

{comment.text}

); }

**Testy E2E wygenerowane przez TestGEN (Playwright):**

import { test, expect } from \'@playwright/test\'; test(\'XSS protection
in comments\', async ({ page }) =\> { await
page.goto(\'http://localhost:3000/comments\'); // Próba wstrzyknięcia
XSS const xssPayload = \'\'; await page.fill(\'#comment-input\',
xssPayload); await page.click(\'#submit-comment\'); // Sprawdź, że
skrypt nie został wykonany page.on(\'dialog\', dialog =\> { throw new
Error(\'XSS vulnerability: alert was triggered!\'); }); // Sprawdź, że
tekst jest wyświetlony jako plain text, nie jako HTML const commentText
= await page.textContent(\'.comment\'); expect(commentText).toContain(\'
