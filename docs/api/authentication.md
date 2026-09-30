# Uwierzytelnianie

TestGEN przyjmuje dwa rodzaje poświadczeń w tym samym nagłówku
`Authorization: Bearer <token>`. O tym, który mechanizm zadziała, decyduje
sam token: prefiks `tgn_` oznacza klucz API, wszystko inne jest traktowane
jak token JWT.

| Sposób | Do czego służy | Jak go zdobyć |
| --- | --- | --- |
| Klucz API | automatyzacja, CI/CD, skrypty | *Ustawienia → Klucze API* |
| Token JWT | interfejs webowy, sesja użytkownika | logowanie `POST /api/v1/auth/login` |

## Klucze API

Klucz ma postać `tgn_` + 64 znaki szesnastkowe i jest pokazywany **tylko raz**,
w chwili utworzenia. TestGEN przechowuje wyłącznie jego skrót SHA‑256 — nie ma
sposobu, by odzyskać klucz po zamknięciu okna. Jeśli go zgubisz, odwołaj stary
i utwórz nowy.

```bash
curl -X GET 'https://api.testgen.io/api/v1/projects' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

### Zakres klucza

| Zakres | Dozwolone metody | Typowe zastosowanie |
| --- | --- | --- |
| `read_only` | `GET`, `HEAD`, `OPTIONS` | pobieranie wyników, dashboardy, monitoring |
| `full_access` | wszystkie | pipeline CI/CD, który wysyła kod i uruchamia analizę |

Klucz `read_only` użyty do `POST`, `PUT` czy `DELETE` dostaje `403` z opisem
`API key ma scope read-only`. Zakresu nie da się zmienić po utworzeniu —
potrzebny jest nowy klucz.

### Czego kluczem API zrobić nie można

Klucz **nie pozwala** zakładać kolejnych kluczy ani webhooków wychodzących.
Te operacje wymagają zalogowanej sesji i kończą się `403`, jeśli spróbujesz
ich kluczem. Powód jest prosty: klucz `full_access`, który potrafiłby
wyprodukować sobie następny albo skonfigurować webhook wynoszący dane na
zewnątrz, byłby furtką omijającą kontrolę właściciela firmy.

### Wygaśnięcie i odwołanie

Klucz może mieć datę wygaśnięcia (maksymalnie dwa lata) albo działać
bezterminowo. Po wygaśnięciu lub odwołaniu API zwraca `401` z rozróżnionym
powodem:

| Sytuacja | `detail` w odpowiedzi |
| --- | --- |
| klucz nieznany | `Nieprawidłowy klucz API` |
| klucz odwołany | `API key został odwołany` |
| klucz wygasł | `API key wygasł` |

Rozróżnienie jest celowe: komunikat trafia do logów Twojego pipeline'u, więc
od razu wiadomo, czy odnowić klucz, czy szukać literówki w konfiguracji.

Kolumna *Ostatnie użycie* na liście kluczy aktualizuje się co najwyżej raz na
pięć minut — przy pipelinie uderzającym kilkaset razy na minutę zapis przy
każdym żądaniu byłby czystym kosztem.

## Token JWT

Logowanie zwraca token dostępu i token odświeżający. Token dostępu wędruje
w nagłówku `Authorization` albo w ciasteczku `access_token` (tak korzysta
z API interfejs webowy).

```bash
curl -X POST 'https://api.testgen.io/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"email": "qa@twojafirma.pl", "password": "twoje-haslo"}'
```

Gdy na koncie włączone jest MFA, logowanie zwraca token pośredni i wymaga
potwierdzenia kodem przez `POST /api/v1/auth/mfa/verify`.

Token dostępu wygasa; odnawia się go przez `POST /api/v1/auth/refresh`.
Wylogowanie unieważnia token natychmiast — nie czeka na wygaśnięcie.

## Kontekst firmy

Jedno konto może należeć do kilku firm. Token JWT niesie w sobie firmę, w której
kontekście działasz, a klucz API jest na stałe związany z firmą, w której
powstał. Wszystkie dane są izolowane per firma — kluczem z firmy A nie
odczytasz projektów firmy B, nawet znając ich identyfikatory.

Klucz API nigdy nie działa jako administrator platformy, a rola wynika
z przypisania jego właściciela do firmy: klucz nie podnosi uprawnień.

## Zobacz też

- [Limity żądań](rate-limiting.md) — progi, nagłówki i obsługa `429`
- [Błędy](errors.md) — format RFC 7807 i lista kodów
- [Przykłady SDK](sdk-examples.md) — gotowy kod w trzech językach
- [Endpointy: uwierzytelnianie](endpoints/auth.md) — pełna referencja

[↩ Powrót do spisu treści](index.md)
