"""LLM prompts for requirement extraction — Epic 2.

This module contains prompts for LLM-based requirement extraction from
Polish technical documentation.
"""

from __future__ import annotations


# Main requirement extraction prompt
REQUIREMENT_EXTRACTION_PROMPT = """Jesteś ekspertem w analizie dokumentacji technicznej. Twoim zadaniem jest wyodrębnienie wszystkich wymagań (funkcjonalnych i niefunkcjonalnych) z poniższego tekstu.

## Instrukcje wyodrębniania:

### Rodzaje wymagań:

1. **Wymagania funkcjonalne** - co system MA robić:
   - Funkcje, które system wykonuje
   - Interakcje z użytkownikiem
   - Przetwarzanie danych
   - Integracje z innymi systemami
   - Właściwości biznesowe

2. **Wymagania niefunkcjonalne** - jak system MA działać:
   - Wydajność (czas odpowiedzi, przepustowość)
   - Bezpieczeństwo (szyfrowanie, autoryzacja)
   - Dostępność (uptime, redundancja)
   - Skalowalność
   - Używalność
   - Zgodność ze standardami

### Wskazówki:

- Wyławiaj wymagania BOTH jawne (zaczynające od "system musi", "wymagane jest") AND implicit (ukryte w opisie funkcji)
- Zwracaj uwagę na wymagania wynikające z integracji (np. "system wysyła email" → wymaga SMTP)
- Każde wymaganie powinno być samodzielnym, kompletnym zdaniem
- Zachowuj oryginalną treść wymagania (nie parafrazuj, chyba że necessary dla jasności)
- Priorytet wywnioskuj z kontekstu (słowa: "krytyczne", "musi", "niezbędny" = critical)

### Format wyjściowy:

Zwróć TYLKO JSON z listą wymagań:
```json
{{
  "requirements": [
    {{
      "text": "dokładna treść wymagania w oryginalnym języku",
      "type": "functional|non-functional",
      "priority": "critical|high|medium|low|null",
      "reasoning": "krótkie uzasadnienie dlaczego to jest wymaganie (max 100 znaków)"
    }}
  ]
}}
```

### Ograniczenia:

- Jeśli tekst nie zawiera wymagań, zwróć pustą listę: {{"requirements": []}}
- Maksymalnie 50 wymagań z jednego fragmentu
- Zignoruj sekcje typu "przykłady", "rysunek", "notatka"

---

## Fragment dokumentu:

```text
{document_content}
```

---

Zwróć TYLKO JSON. Bez żadnych dodatkowych komentarzy.
"""


# Chunking prompt for large documents
CHUNKING_INSTRUCTION = """
Dokument został podzielony na fragmenti. Przeanalizuj każdy fragment niezależnie.
Wymagania mogą być rozdzielone między fragmenty - to jest normalne.
"""


# Few-shot examples for better extraction
REQUIREMENT_EXTRACTION_EXAMPLES = """
## Przykłady:

### Przykład 1:
```
System musi pozwalać użytkownikom na rejestrację konta przy użyciu adresu email i hasła.
Hasło musi mieć minimum 8 znaków i zawierać wielką literę, małą literę oraz cyfrę.
```
→
```json
{{
  "requirements": [
    {{
      "text": "System musi pozwalać użytkownikom na rejestrację konta przy użyciu adresu email i hasła.",
      "type": "functional",
      "priority": "high",
      "reasoning": "Funkcja rejestracji użytkowników"
    }},
    {{
      "text": "Hasło musi mieć minimum 8 znaków i zawierać wielką literę, małą literę oraz cyfrę.",
      "type": "non-functional",
      "priority": "high",
      "reasoning": "Wymaganie dotyczące jakości hasła (bezpieczeństwo)"
    }}
  ]
}}
```

### Przykład 2:
```
API powinno odpowiadać w czasie poniżej 200ms dla 95% zapytań.
Wymagane jest szyfrowanie TLS 1.3 dla wszystkich połączeń.
```
→
```json
{{
  "requirements": [
    {{
      "text": "API powinno odpowiadać w czasie poniżej 200ms dla 95% zapytań.",
      "type": "non-functional",
      "priority": "high",
      "reasoning": "Wymaganie wydajności (czas odpowiedzi)"
    }},
    {{
      "text": "Wymagane jest szyfrowanie TLS 1.3 dla wszystkich połączeń.",
      "type": "non-functional",
      "priority": "critical",
      "reasoning": "Wymaganie bezpieczeństwa (szyfrowanie)"
    }}
  ]
}}
```

### Przykład 3 (tekst bez jawnych wymagań):
```
Rysunek 2 pokazuje architekturę systemu.
Moduł logowania zapisuje informacje o autoryzacji do bazy danych PostgreSQL.
```
→
```json
{{
  "requirements": [
    {{
      "text": "Moduł logowania zapisuje informacje o autoryzacji do bazy danych PostgreSQL.",
      "type": "functional",
      "priority": "medium",
      "reasoning": "Opis funkcji systemu (implicit requirement)"
    }}
  ]
}}
```

### Przykład 4 (sekcja bez wymagań):
```
Patrz rozdział 3.2 dla szczegółów implementacji.
Powyższy opis ma charakter orientacyjny.
```
→
```json
{{
  "requirements": []
}}
```

---

Pamiętaj: Szukaj wymagań zarówno w jawnych deklaracjach ("musi", "wymagane"), jak i w opisach funkcji ("moduł wykonuje", "system pozwala").
"""


def build_extraction_prompt(
    document_content: str,
    section_title: str | None = None,
    max_length: int = 8000,
) -> str:
    """Build complete requirement extraction prompt.

    Args:
        document_content: Raw text from document section
        section_title: Optional section title for context
        max_length: Maximum content length to send to LLM

    Returns:
        Complete prompt string ready for LLM
    """
    # Truncate content if too long
    content = document_content[:max_length]
    if len(document_content) > max_length:
        content += "\n... (tekst skrócony)"

    prompt = REQUIREMENT_EXTRACTION_PROMPT.format(document_content=content)

    # Add section context if available
    if section_title:
        context = f"\n\n## Kontekst: Analiza sekcji '{section_title}'"
        prompt = prompt.replace("## Fragment dokumentu:", context + "\n\n## Fragment dokumentu:")

    return prompt


def build_hybrid_merge_prompt(
    native_requirements: list[dict],
    llm_requirements: list[dict],
) -> str:
    """Build prompt for merging native and LLM extracted requirements.

    Args:
        native_requirements: Requirements from native extractor
        llm_requirements: Requirements from LLM extractor

    Returns:
        Prompt for intelligent merge
    """
    return f"""Jesteś ekspertem w analizie wymagań. Dostałeś dwie listy wymagań wyekstrahowane z tego samego dokumentu:

## Wymagania z ekstraktora natywnego ({len(native_requirements)} sztuk):
{format_requirements_list(native_requirements)}

## Wymagania z ekstraktora LLM ({len(llm_requirements)} sztuk):
{format_requirements_list(llm_requirements)}

---

## Zadanie:

Połącz oba zestawy w jedną listę bez duplikatów.

Zasady łączenia:
1. Jeśli to samo wymaganie występuje w obu → zachowaj wersję LLM (jest precyzyjniejsza)
2. Jeśli wersje się różnią → zachowaj tę z wyższym priorytetem
3. Jeśli requirement występuje tylko w jednym zestawie → zachowaj go
4. Zduplikowane = podobna treść (similarity > 80%)

Zwróć JSON:
```json
{{
  "merged_requirements": [
    {{
      "text": "treść wymagania",
      "type": "functional|non-functional",
      "priority": "critical|high|medium|low|null",
      "source": "native|llm|both",
      "reasoning": "uzasadnienie"
    }}
  ]
}}
```

Zwróć TYLKO JSON.
"""


def format_requirements_list(requirements: list[dict]) -> str:
    """Format requirements list for display in prompt.

    Args:
        requirements: List of requirement dictionaries

    Returns:
        Formatted string representation
    """
    if not requirements:
        return "(brak)"

    lines = []
    for i, req in enumerate(requirements[:20], 1):  # Show max 20
        lines.append(f"{i}. [{req.get('type', '?')}] {req.get('text', '')[:80]}...")

    if len(requirements) > 20:
        lines.append(f"... i {len(requirements) - 20} więcej")

    return "\n".join(lines)
