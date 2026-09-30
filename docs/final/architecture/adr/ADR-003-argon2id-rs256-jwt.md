# ADR-003: Argon2id + RS256 JWT (asymmetric)

## Status

Accepted

## Kontekst

Platforma przetwarza zastrzeżony kod i wymaga solidnego uwierzytelniania:
odporne na ataki brute-force hashowanie haseł, rotacja kluczy oraz możliwość
weryfikacji tokenu w wielu serwisach bez udostępniania klucza prywatnego.
Tokeny przesyłane w ciasteczkach są podatne na kradzież przez XSS, stąd
wymóg HttpOnly + podpisywanie asymetryczne.

## Decyzja

- **Hashowanie haseł:** Argon2id (memory-hard, parametry zgodne z OWASP).
- **Tokeny sesji:** JWT podpisywane **RS256** (asymetrycznie). Klucz prywatny
  trzymany po stronie backendu (`keys/private.pem`), klucz publiczny
  (`keys/public.pem`) udostępniany każdemu serwisowi weryfikującemu.
- **Transport:** JWT w **HttpOnly cookie** (`access_token`, `refresh_token`),
  z flagami `Secure`, `SameSite`. Endpointy akceptują również nagłówek
  `Authorization: Bearer` dla klientów nieprzeglądarkowych (CLI, SDK).
- **MFA:** opcjonalne TOTP (Fernet jako szyfrowanie sekretów MFA,
  `ENCRYPTION_KEY`).

## Konsekwencje

**Pozytywne:**

- Asymetryczne JWT: serwery weryfikują token kluczem publicznym, bez dostępu do
  prywatnego — mniejsza powierzchnia ataku.
- HttpOnly cookie chroni token przed kradzieżą przez XSS.
- Argon2id uodparnia hasła na ataki GPU/ASIC.
- Rotacja kluczy możliwa bez wymiany sekretu we wszystkich serwisach.

**Negatywne:**

- Wymaga zarządzania parą kluczy (generacja, przechowywanie, rotacja).
- MFA zwiększa złożoność przepływu logowania.
- RS256 jest wolniejszy w podpisywaniu niż HS256 (akceptowalne dla sesji).

## Powiązane

- [environment-setup.md](../../deployment-guide/environment-setup.md) — zmienne `JWT_*`,
  `ENCRYPTION_KEY`.
- [api/examples/auth_examples.md](../api/examples/auth_examples.md) —
  przykłady logowania, refresh, MFA.
