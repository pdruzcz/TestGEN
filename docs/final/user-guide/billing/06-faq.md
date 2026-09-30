# FAQ — moduł billingowy

> Dokumentacja P2, Epic 7.

## Płatności

**Czy mogę płacić rocznie?**
Nie. Jedyny cykl to miesięczny (30/50 PLN), decyzja produktowa z 2026-08-28.

**Jakie metody płatności obsługuje tpay w TestGEN?**
BLIK (z Płatnościami Powtarzalnymi), karta (3-D Secure, z możliwością
zapisania) oraz przelew/PBL — wybór następuje w Panelu Transakcyjnym tpay.

**Czy muszę zapisywać kartę?**
Nie — ale bez zapisanej metody (karta lub aktywny alias BLIK) odnowienie
miesięczne nie powiedzie się i po dunningu (7 dni łaski) plan wróci do
Freemium.

**Płacę BLIK, ale mój bank odmawia.**
Twój bank nie obsługuje Płatności Powtarzalnych BLIK. Zapłać kartą
i zapisz ją jako metodę — odnowienia będą obciążać kartę.

**Dlaczego nie mogę kupić planu, mając już Basic?**
Z aktywnym planem płatnym zakup jest zablokowany (409) — zmiany planu
dokonuje się przez ekran Subskrypcja (upgrade z dopłatą proporcjonalną
albo downgrade na koniec okresu).

## Subskrypcja

**Co się dzieje po anulowaniu?**
Dostęp do planu do końca opłaconego okresu, potem automatyczny Freemium.
Bez utraty danych i bez blokady konta. Do końca okresu możesz reaktywować.

**Czy downgrade zwraca pieniądze?**
Nie — downgrade obowiązuje od końca bieżącego okresu, rozliczenie
kończy się z bieżącym okresem (bez zwrotów).

**Zaplanowałem downgrade — mogę go odwołać?**
Tak, do końca bieżącego okresu (przycisk rezygnacji na ekranie
subskrypcji).

**Nie pomyśliła płatność przy odnowieniu — co teraz?**
System ponawia próby w kolejnych dniach; po ich wyczerpaniu: Freemium
+ 7 dni łaski z limitami płatnego planu. W tym czasie zaktualizuj metodę
płatności albo kup plan ponownie.

## Limity i faktury

**Kiedy resetują się limity?**
Na początku każdego okresu rozliczeniowego (miesięcznego).

**Anulowałem analizę — czy licznik wraca?**
Nie — licznik analiz rośnie o uruchomioną analizę; licznik plików
dotyczy plików w analizie.

**Kiedy dostanę fakturę?**
Automatycznie po każdej opłaconej płatności — mailem z PDF (Owner)
i na liście faktur w portalu.

**Poprawiłem dane fakturowe — czy stara faktura się zmieni?**
Nie. Wystawione faktury trzymają snapshot danych z chwili wystawienia;
nowe dane zadziałają od następnej faktury.

**Kto widzi faktury i transakcje?**
Owner i User — lista faktur oraz historia transakcji. Zakupy, zmiany
planu, dane fakturowe i metody płatności — wyłącznie Owner.
