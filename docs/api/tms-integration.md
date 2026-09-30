# Integracja z systemami zarządzania testami

TestGEN eksportuje przypadki testowe wprost do TestRaila, Jira Xray i Zephyr
Scale — bez przepisywania ich ręcznie. Ponowny eksport **aktualizuje** testy
utworzone wcześniej, zamiast tworzyć duplikaty.

Konfiguracja jest **per projekt**, bo identyfikator projektu docelowego różni
się między projektami TestGEN.

## Warunek wspólny: pole własne `testgen_id`

Deduplikacja opiera się na identyfikatorze przypadku z TestGEN, zapisanym po
stronie TMS. To jedyne pewne powiązanie — tytuł testu może się zmienić, a wtedy
ponowny eksport zrobiłby duplikat zamiast aktualizacji.

**Bez założenia tego pola każdy eksport utworzy nowe przypadki.** Duplikaty
w TMS sprząta się ręcznie, jeden po drugim, więc warto to skonfigurować przed
pierwszym eksportem.

| System | Gdzie trafia znacznik | Co trzeba przygotować |
| --- | --- | --- |
| TestRail | pole własne `testgen_id` | *Administration → Customizations* → pole tekstowe `testgen_id` |
| Xray | etykieta `testgen-{uuid}` | nic — etykiety powstają same |
| Zephyr Scale | pole własne `testgen_id` | pole własne typu tekstowego w projekcie |

Xray wypada tu najwygodniej: testy są w nim zgłoszeniami Jiry, a etykiety są
przeszukiwalne JQL‑em bez konfigurowania czegokolwiek w instancji klienta.

## Jak przebiega eksport

Eksport idzie **w tle**. Wszystkie trzy systemy ograniczają tempo żądań, więc
setka przypadków to setka wywołań w odstępach i kilka minut pracy — żądanie HTTP
o takim czasie odpowiedzi padłoby na limicie czasu serwera pośredniczącego.

1. Wybierasz przypadki na liście testów (albo nic nie zaznaczasz — wtedy
   eksportowane są wszystkie przypadki projektu).
2. TestGEN pobiera **raz** listę istniejących testów i buduje indeks po
   znaczniku. Szukanie osobnym żądaniem dla każdego przypadku byłoby przy
   limitach tempa wielokrotnie wolniejsze.
3. Dla każdego przypadku: znaleziony znacznik → aktualizacja, brak → utworzenie.
4. Otrzymujesz identyfikator zadania; postęp śledzisz pod
   `GET /api/v1/tasks/{task_id}`.

Błąd pojedynczego przypadku **nie przerywa** eksportu — raport wymienia go
osobno, z powodem. Przy setce testów jeden odrzucony przez walidację nie może
unieważnić pozostałych.

Eksport nie jest ponawiany automatycznie: powtórzenie utworzyłoby testy, które
już powstały. Powtórkę uruchamiasz świadomie, a dzięki deduplikacji aktualizuje
ona istniejące przypadki.

## TestRail

Ekran: *Projekt → Integracja TestRail* (`/projects/{id}/integrations/testrail`)

### Konfiguracja

| Pole | Skąd je wziąć |
| --- | --- |
| Adres instancji | np. `https://twojafirma.testrail.io` (wymagany HTTPS) |
| E‑mail | konto TestRail, którym eksportujesz |
| Klucz API | *My Settings → API Keys* w TestRailu |
| Identyfikator projektu | liczba z adresu projektu w TestRailu |
| Suite | tylko w trybie multi‑suite |

Po zapisaniu użyj **Testuj połączenie** — wywołuje `get_project` i nie tworzy
żadnych zasobów.

### Mapowanie pól

| TestGEN | TestRail |
| --- | --- |
| tytuł | `title` |
| priorytet | `priority_id` (konfigurowalne) |
| typ testu | `type_id` (konfigurowalne) |
| warunki wstępne | `custom_preconds` |
| kroki | `custom_steps_separated` |
| oczekiwany rezultat | `custom_expected` |
| identyfikator TestGEN | `custom_testgen_id` |

Identyfikatory priorytetów i typów **zależą od instancji** — domyślne wartości
odpowiadają standardowej konfiguracji TestRaila. Sprawdź swoje
w *Administration → Customizations* i popraw w tabeli mapowania.

Kroki idą w formacie „separated", dzięki czemu TestRail renderuje je jako
tabelę, a nie jeden blok tekstu.

### Sekcje

Sekcja powstaje automatycznie, per moduł przypadku (klasa albo funkcja
źródłowa). Przypadki bez modułu trafiają do wspólnej sekcji `TestGEN`.
Istniejące sekcje są rozpoznawane bez względu na wielkość liter.

## Jira Xray

Ekran: *Projekt → Integracja Jira* (`/projects/{id}/integrations/jira`),
wtyczka **Jira Xray**

### Konfiguracja

| Pole | Skąd je wziąć |
| --- | --- |
| Adres instancji | np. `https://twojafirma.atlassian.net` |
| E‑mail | konto Atlassian |
| Token API | *id.atlassian.com → Security → API tokens* |
| Klucz projektu | prefiks zgłoszeń, np. `QA` w `QA-123` |
| Powiązane zgłoszenie | opcjonalnie: historyjka lub wymaganie |

### Jak Xray przechowuje testy

Testy są zgłoszeniami Jiry typu **Test**. Powiązanie z TestGEN idzie
w etykiecie `testgen-{uuid}`, obok Twoich własnych etykiet.

**Aktualizacja scala etykiety, a nie nadpisuje.** Jeśli zespół dopisał do testu
etykiety sprintu czy komponentu, przetrwają kolejny eksport.

| TestGEN | Xray |
| --- | --- |
| tytuł | `summary` |
| opis / warunki wstępne | `description` |
| priorytet | `priority.name` (konfigurowalne, np. `Highest`) |
| typ testu | etykieta (np. `typ-bezpieczenstwa`) |
| kroki | `steps[].action` |
| oczekiwany rezultat | `steps[].result` ostatniego kroku |

Priorytety Jiry adresuje się **nazwą**, nie liczbą jak w TestRailu. Typ testu
trafia do etykiety, a nie do komponentu — komponenty trzeba wcześniej założyć
w projekcie, etykiety powstają same.

Podanie *powiązanego zgłoszenia* sprawia, że każdy nowo utworzony test zostanie
z nim powiązany. Nieudane powiązanie (np. brak uprawnień) **nie unieważnia**
utworzonego testu — zostanie zalogowane, a eksport pójdzie dalej.

## Zephyr Scale

Ekran: ten sam co dla Xraya, wtyczka **Zephyr Scale**

Projekt korzysta z jednej wtyczki naraz — wybranie Zephyra dezaktywuje
konfigurację Xraya i odwrotnie. Inaczej eksport nie wiedziałby, której użyć.

### Jak Zephyr przechowuje testy

Zephyr ma własny magazyn testów, niezależny od zgłoszeń Jiry, i własne klucze
(`QA-T1`). Znacznik TestGEN trafia do pola własnego `testgen_id`.

| TestGEN | Zephyr Scale |
| --- | --- |
| tytuł | `name` |
| opis | `objective` |
| warunki wstępne | `precondition` |
| priorytet | `priority` (nazwa) |
| kroki | `testScript.steps[].description` |
| oczekiwany rezultat | `expectedResult` ostatniego kroku |
| identyfikator TestGEN | `customFields.testgen_id` |

### Foldery

Foldery powstają automatycznie, per moduł, pod wspólnym korzeniem `/TestGEN`.
Odrzucenie duplikatu nazwy przez Zephyra jest traktowane jako „folder już
istnieje", nie jako błąd.

## Synchronizacja dwukierunkowa

Eksport wysyła przypadki w jedną stronę. Synchronizacja dokłada kierunek
powrotny i cykl: co jakiś czas TestGEN sam sięga do TMS-a, wnosi tamtejsze
zmiany i odsyła swoje.

### Ustawienia

```bash
curl -X PUT "$TESTGEN_API_URL/api/v1/integrations/$INTEGRATION_ID/sync/config" \
  -H "Authorization: Bearer $TESTGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "direction": "bidirectional",
        "interval_minutes": 15,
        "conflict_strategy": "last_write_wins"
      }'
```

| Pole | Wartości | Znaczenie |
| --- | --- | --- |
| `direction` | `push`, `pull`, `bidirectional` | co jest wysyłane, a co pobierane |
| `interval_minutes` | 5–1440 | jak często; poniżej 5 minut API odmawia |
| `conflict_strategy` | `last_write_wins`, `manual` | co zrobić, gdy zmiana nastąpiła po obu stronach |

Zapis ustawień **nie uruchamia** synchronizacji — służy do tego
`POST /sync/activate`. Rozdzielenie jest celowe: poprawka odstępu nie może
po cichu zacząć wysyłać przypadków do TMS-a.

Dolna granica pięciu minut nie jest umowna: TestRail i Jira dławią tempo
żądań, więc pełny przebieg po setce przypadków i tak trwa dłużej.

### Przebieg

Zaplanowane przebiegi rozsyła zadanie cykliczne co pięć minut; podejmuje te
synchronizacje, których odstęp właśnie minął. Pojedynczy przebieg robi
najpierw **pull**, potem **push** — odwrotna kolejność wysyłałaby do TMS-a
wersję sprzed rozstrzygnięcia konfliktu i natychmiast ją cofała.

Ręczne uruchomienie, bez czekania na odstęp:

```bash
curl -X POST "$TESTGEN_API_URL/api/v1/integrations/$INTEGRATION_ID/sync/run" \
  -H "Authorization: Bearer $TESTGEN_API_KEY"
```

Odpowiedź niesie `task_id`; postęp śledzi się przez `/api/v1/tasks/{task_id}`.

### Co wraca z TMS-a

Kierunek TMS → TestGEN przenosi tytuł, opis, kroki, oczekiwany wynik
i priorytet. Kod testu i metadane analizy zostają nietknięte — powstają
w TestGEN i nie mają odpowiednika po drugiej stronie, więc ściąganie ich
z powrotem mogłoby je tylko wymazać.

Puste pole po stronie TMS-a nie kasuje wartości w TestGEN. Większość
instancji nie wypełnia wszystkich pól, a synchronizacja nie może być powodem
utraty opisu, którego nikt nie tknął.

Przypadek obecny w TMS-ie, a nieobecny w TestGEN, jest pomijany — kierunek
powrotny nie zna wyniku analizy, do którego musiałby taki przypadek podpiąć.

### Konflikty

Konflikt to sytuacja, w której ten sam przypadek zmienił się po obu stronach
od ostatniego przebiegu. Pierwszy przebieg nie może dać konfliktu: bez punktu
odniesienia „obie strony zmienione" nie ma znaczenia.

* `last_write_wins` — wygrywa nowszy `updated_at`.
* `manual` — nic nie jest nadpisywane; konflikt czeka na decyzję człowieka.

**Konflikt zapisujemy zawsze**, również wtedy, gdy reguła rozstrzygnęła go
sama. Przegrana wersja jest jedynym śladem po nadpisanych danych.

```bash
curl "$TESTGEN_API_URL/api/v1/integrations/$INTEGRATION_ID/sync/conflicts?resolution=pending" \
  -H "Authorization: Bearer $TESTGEN_API_KEY"

curl -X POST "$TESTGEN_API_URL/api/v1/sync/conflicts/$CONFLICT_ID/resolve" \
  -H "Authorization: Bearer $TESTGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"resolution": "tms_wins"}'
```

`tms_wins` wnosi zapamiętaną wersję TMS-a do przypadku. `testgen_wins` nie
zmienia niczego lokalnie — wersja TestGEN już tam jest i trafi do TMS-a przy
najbliższym pushu. Raz rozstrzygniętego konfliktu nie da się rozstrzygnąć
powtórnie.

### Gdy TMS przestaje odpowiadać

Po trzech nieudanych przebiegach z rzędu synchronizacja dostaje stan
`degraded`, a Owner firmy — jednego maila. Trzy, a nie jeden, bo pojedynczy
timeout zdarza się przy każdym wdrożeniu po stronie TMS-a; jeden, a nie przy
każdej porażce, bo mail co kwadrans nauczyłby odbiorcę go ignorować.

Próby są ponawiane dalej, w normalnym rytmie. Pierwszy udany przebieg
przywraca stan `active` bez żadnej akcji ze strony użytkownika.

Stan podgląda się jednym żądaniem:

```bash
curl "$TESTGEN_API_URL/api/v1/integrations/$INTEGRATION_ID/sync/status" \
  -H "Authorization: Bearer $TESTGEN_API_KEY"
```

### Powiązanie widoczne na przypadku

Po pierwszym przebiegu przypadek testowy niesie `tms_external_id`
i `tms_synced_at`, a lista przypadków pokazuje plakietkę z identyfikatorem
po stronie TMS-a.

## Rozwiązywanie problemów

| Objaw | Przyczyna | Co zrobić |
| --- | --- | --- |
| Każdy eksport tworzy duplikaty | brak pola własnego `testgen_id` w TMS | załóż pole (patrz na początku); wcześniejsze duplikaty trzeba usunąć ręcznie |
| „Odrzucił poświadczenia" | zły klucz/token albo e‑mail | wygeneruj nowy klucz; w Jirze użyj tokenu API, nie hasła |
| „Brak uprawnień" | konto nie ma prawa tworzyć testów w projekcie | sprawdź uprawnienia konta w projekcie docelowym |
| „Wtyczka nie jest zainstalowana" (`404`) | Xray/Zephyr nieobecny w instancji | zweryfikuj, czy wtyczka jest zainstalowana i aktywna |
| „Ograniczył tempo żądań" | instancja ma ostrzejszy limit niż domyślny | ponów eksport później, mniejszymi paczkami |
| Część przypadków ma status „nieudany" | walidacja po stronie TMS | sprawdź powód w raporcie; najczęściej to nieprawidłowe mapowanie `priority_id`/`type_id` |
| Testy trafiły do złej wtyczki | projekt skonfigurowany na inną | eksport niezgodny z konfiguracją kończy się `422` — zmień konfigurację albo użyj właściwego przycisku |
| Priorytety nie zgadzają się z TestRailem | domyślne mapowanie nie pasuje do instancji | popraw tabelę mapowania w konfiguracji |
| Synchronizacja w stanie „wymaga uwagi" | trzy nieudane próby z rzędu | sprawdź `last_error` w `/sync/status`; po usunięciu przyczyny stan wróci sam |
| Zmiany z TMS-a nie wracają | kierunek ustawiony na `push` | zmień `direction` na `pull` albo `bidirectional` |
| Konflikty piętrzą się bez rozstrzygnięcia | strategia `manual` | rozstrzygnij je na ekranie synchronizacji albo przełącz na `last_write_wins` |
| Przypadek z TMS-a nie pojawia się w TestGEN | kierunek powrotny nie zakłada nowych przypadków | wyeksportuj go najpierw z TestGEN — synchronizacja dopasowuje po `testgen_id` |

## Zobacz też

- [Endpointy: integracje](endpoints/integrations.md)
- [Endpointy: przypadki testowe](endpoints/test-cases.md)
- [Uwierzytelnianie](authentication.md)

[↩ Powrót do spisu treści](index.md)
