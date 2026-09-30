"""LLM prompts for document classification — Epic 2.

This module contains prompts for LLM-based document type classification.
LLM classification provides higher accuracy (>90%) compared to native rules (>80%).
"""

from __future__ import annotations


# Main classification prompt
DOCUMENT_CLASSIFICATION_PROMPT = """Jesteś ekspertem w analizie dokumentacji technicznej. Twoim zadaniem jest sklasyfikować podany fragment dokumentu do jednego z następujących typów:

## Dostępne typy dokumentów:

### 1. specyfikacja_wymagań (Specyfikacja Wymagań / SRS / BRD / FRD)
Dokumenty opisujące wymagania systemu, funkcjonalne i niefunkcjonalne.
**Cechy charakterystyczne:**
- Sekcje: "Wymagania funkcjonalne", "Wymagania niefunkcjonalne", "Aktorzy/Interesariusze"
- Wzorce: "UC-001", "FR-01", "NFR-01" (identyfikatory wymagań)
- Struktura: 1. Wprowadzenie, 2. Zakres, 3. Wymagania, 4. Interfejsy
- Słowa kluczowe: wymaganie, akceptacja, kryterium, przypadek użycia, stakeholder, priorytet

### 2. podręcznik_użytkownika (Podręcznik Użytkownika / User Manual)
Dokumenty pomocy dla użytkowników końcowych.
**Cechy charakterystyczne:**
- Sekcje: "Pierwsze kroki", "Instalacja", "Jak użyć", "Interfejs użytkownika"
- Instrukcje krok po kroku: "Krok 1", "Step 1"
- Zrzuty ekranów: "Rysunek 1", "Figure 1"
- Słowa kluczowe: użytkownik, instrukcja, obsługa, kliknij, wybierz, formularz

### 3. instrukcja_techniczna (Instrukcja Techniczna / Admin Guide)
Dokumenty dla administratorów i deweloperów.
**Cechy charakterystyczne:**
- Sekcje: "Wymagania systemowe", "Instalacja", "Konfiguracja", "Architektura"
- Treść techniczna: baza danych, serwer, API, wdrożenie
- Słowa kluczowe: instalacja, konfiguracja, wdrożenie, deployment, infrastruktura

### 4. opis_api (Opis API / API Documentation)
Dokumenty opisujące interfejsy programistyczne.
**Cechy charakterystyczne:**
- Sekcje: "Authentication", "Endpoints", "Metody", "Request/Response"
- Przykłady: curl, HTTP, JSON
- Słowa kluczowe: endpoint, POST, GET, JSON, request, response, parametr, swagger

### 5. notatki_projektowe (Notatki Projektowe / Meeting Notes)
Dokumenty z spotkań, decyzje, plany.
**Cechy charakterystyczne:**
- Sekcje: "Agenda", "Decyzje", "Action items", "Dyskusja"
- Format listy: checkboxy, TODO
- Słowa kluczowe: spotkanie, decyzja, zadanie, dyskusja, protokół

### 6. inny (Inne)
Dokumenty niepasujące do powyższych kategorii.

---

## Fragment dokumentu do analizy:

```text
{document_content}
```

---

## Instrukcja:

Zwróć JSON w następującym formacie:
```json
{{
  "type": "TYP_DOKUMENTU",
  "confidence": 0-100,
  "reasoning": "Krótkie uzasadnienie (po polsku, max 200 znaków)"
}}
```

**type** - jedna z wartości: specyfikacja_wymagań, podręcznik_użytkownika, instrukcja_techniczna, opis_api, notatki_projektowe, inny
**confidence** - pewność klasyfikacji (0-100)
**reasoning** - dlaczego taki typ, na podstawie jakich cech

Zwróć TYLKO JSON, bez żadnych dodatkowych komentarzy.
"""


# Hybrid classification prompt (uses both native and LLM results)
HYBRID_CLASSIFICATION_PROMPT = """Jesteś ekspertem w analizie dokumentacji technicznej. Dostałeś wyniki klasyfikacji z dwóch metod:

## Wynik klasyfikacji natywnej (reguły NLP):
- Typ: {native_type}
- Pewność: {native_confidence}%

## Wynik klasyfikacji LLM:
- Typ: {llm_type}
- Pewność: {llm_confidence}%
- Uzasadnienie: {llm_reasoning}

## Fragment dokumentu:

```text
{document_content}
```

---

## Zadanie:

Zdecyduj, który wynik jest bardziej wiarygodny i zwróć finalną klasyfikację.

Zwróć JSON:
```json
{{
  "type": "WYBRANY_TYP_DOKUMENTU",
  "confidence": 0-100,
  "reasoning": "Dlaczego wybrano ten wynik (max 200 znaków)"
}}
```

Jeśli oba wyniki są zgodne → przyjmij wysoką pewność (90-100).
Jeśli wyniki się różnią → rozstrzygnij na podstawie analizy treści.

Zwróć TYLKO JSON.
"""


# Few-shot examples for better classification
CLASSIFICATION_EXAMPLES = """
## Przykłady:

### Przykład 1:
```
2. Wymagania funkcjonalne
2.1 Rejestracja użytkownika (UC-001)
Użytkownik musi mieć możliwość założenia konta...
2.2 Logowanie (UC-002)
System wymaga podania loginu i hasła...
```
→ {{"type": "specyfikacja_wymagań", "confidence": 95, "reasoning": "Wyraźna struktura wymagań z identyfikatorami UC"}}

### Przykład 2:
```
Pierwsze kroki
1. Zainstaluj aplikację
2. Uruchom instalator.exe
3. Postępuj zgodnie z instrukcjami na ekranie
```
→ {{"type": "podręcznik_użytkownika", "confidence": 92, "reasoning": "Instrukcja krok po kroku dla użytkownika"}}

### Przykład 3:
```
POST /api/v1/users
Content-Type: application/json

{{
  "name": "Jan Kowalski",
  "email": "jan@example.com"
}}

Response: 201 Created
```
→ {{"type": "opis_api", "confidence": 98, "reasoning": "Przykładowe żądanie HTTP i odpowiedź"}}

### Przykład 4:
```
Spotkanie projektowe - 15.01.2025
Agenda:
1. Status integracji modułu płatności
2. Problemy z wydajnością bazy danych
3. Decyzja: Przeniesienie na PostgreSQL 16

Action items:
- Anna: Przygotować plan migracji do 20.01
- Piotr: Benchmark nowej bazy
```
→ {{"type": "notatki_projektowe", "confidence": 94, "reasoning": "Format protokołu spotkania z agenda i action items"}}

---

Powyższe przykłady są tylko orientacyjne. Skup się na dostarczonym fragmencie dokumentu.
"""


def build_classification_prompt(
    document_content: str,
    max_length: int = 8000,
) -> str:
    """Build complete classification prompt with document content.

    Args:
        document_content: Raw text from document to classify
        max_length: Maximum content length to send to LLM

    Returns:
        Complete prompt string ready for LLM
    """
    # Truncate content if too long
    content = document_content[:max_length]
    if len(document_content) > max_length:
        content += "\n... (tekst skrócony)"

    return DOCUMENT_CLASSIFICATION_PROMPT.format(document_content=content)


def build_hybrid_prompt(
    document_content: str,
    native_type: str,
    native_confidence: float,
    llm_type: str,
    llm_confidence: float,
    llm_reasoning: str,
    max_length: int = 6000,
) -> str:
    """Build hybrid classification prompt combining native and LLM results.

    Args:
        document_content: Raw text from document
        native_type: Document type from native classifier
        native_confidence: Confidence from native classifier
        llm_type: Document type from LLM classifier
        llm_confidence: Confidence from LLM classifier
        llm_reasoning: Reasoning from LLM classifier
        max_length: Maximum content length

    Returns:
        Complete hybrid prompt string
    """
    content = document_content[:max_length]
    if len(document_content) > max_length:
        content += "\n... (tekst skrócony)"

    return HYBRID_CLASSIFICATION_PROMPT.format(
        document_content=content,
        native_type=native_type,
        native_confidence=native_confidence,
        llm_type=llm_type,
        llm_confidence=llm_confidence,
        llm_reasoning=llm_reasoning,
    )
