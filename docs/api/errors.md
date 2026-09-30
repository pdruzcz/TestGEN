# Błędy

Wszystkie błędy TestGEN mają format [RFC 7807](https://datatracker.ietf.org/doc/html/rfc7807)
i typ zawartości `application/problem+json`. Dzięki temu obsługa błędów po
stronie klienta jest jedna dla całego API.

```json
{
  "type": "https://testgen.io/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Projekt nie został znaleziony",
  "instance": "/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

| Pole | Znaczenie |
| --- | --- |
| `type` | identyfikator rodzaju błędu (URI) |
| `title` | krótka nazwa rodzaju błędu |
| `status` | kod HTTP, ten sam co w odpowiedzi |
| `detail` | opis konkretnego przypadku, po polsku |
| `instance` | ścieżka żądania, które się nie powiodło |

W kodzie sprawdzaj `status`, a `detail` pokazuj użytkownikowi. `type` jest
stabilny i nadaje się do rozgałęzień logiki; `detail` bywa doprecyzowywany
między wydaniami.

## Kody odpowiedzi

| Kod | Kiedy występuje | Co zrobić |
| :-: | --- | --- |
| `400` | żądanie niepoprawne składniowo | popraw treść żądania |
| `401` | brak, wygasłe albo odwołane poświadczenia | odśwież token albo wymień klucz API |
| `402` | funkcja wymaga wyższego planu | zmień plan albo pomiń moduł |
| `403` | poświadczenia poprawne, brak uprawnień | sprawdź rolę i zakres klucza |
| `404` | zasób nie istnieje lub nie należy do Twojej firmy | zweryfikuj identyfikator |
| `409` | konflikt stanu (np. nazwa zajęta) | zmień dane albo użyj istniejącego zasobu |
| `422` | walidacja treści żądania | popraw pola wskazane w `errors` |
| `429` | przekroczony limit żądań | odczekaj, patrz [Limity żądań](rate-limiting.md) |
| `500` | błąd po stronie TestGEN | ponów; jeśli się powtarza, zgłoś z `instance` i czasem |
| `502` | błąd systemu zewnętrznego (GitHub, Jira, TestRail) | sprawdź poświadczenia i dostępność tamtej usługi |

### `404` zamiast `403` przy cudzych zasobach

Próba odczytu zasobu należącego do innej firmy zwraca `404`, a nie `403`.
To celowe: `403` potwierdzałby, że zasób o takim identyfikatorze istnieje.

## Błędy walidacji (`422`)

Odpowiedź niesie dodatkowe pole `errors` z listą problemów per pole:

```json
{
  "type": "https://testgen.io/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Request validation failed",
  "instance": "/api/v1/webhooks",
  "errors": [
    {
      "type": "string_too_short",
      "loc": ["body", "secret"],
      "msg": "String should have at least 16 characters",
      "input": "krotki"
    }
  ]
}
```

`loc` to ścieżka do pola: pierwszy element mówi, gdzie problem wystąpił
(`body`, `query`, `path`), kolejne wskazują pole w strukturze.

## Błędy systemów zewnętrznych (`502`)

Gdy TestGEN nie może dogadać się z GitHubem, GitLabem, Jirą albo TestRailem,
zwraca `502` z `detail` przepisanym z tamtej usługi — na przykład
`Token GitHuba wygasł lub został odwołany — połącz repozytorium ponownie`.
Ponawianie ma sens tylko przy błędach przejściowych; przy wygasłych
poświadczeniach trzeba je najpierw odnowić.

## Zobacz też

- [Uwierzytelnianie](authentication.md)
- [Limity żądań](rate-limiting.md)

[↩ Powrót do spisu treści](index.md)
