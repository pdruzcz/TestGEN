"""LLM prompt building + response parsing for GUI flow narration — Story 3.9, AC-6."""

import json
import re


def build_flow_prompt(screen_descriptions: list[str], steps) -> str:
    """Build a Polish prompt asking the LLM to narrate each transition.

    ``steps`` is the list of native :class:`FlowStepResult` objects; only their
    sequence + native description are exposed to the model.
    """
    screens_block = "\n".join(screen_descriptions)
    steps_block = "\n".join(
        f"- krok {s.sequence}: {s.action_type} (cel: {s.target_element or 'brak'})" for s in steps
    )
    return (
        "Jesteś analitykiem QA. Na podstawie opisu kolejnych ekranów aplikacji "
        "oraz wykrytych przejść opisz w naturalnym języku polskim, jaką akcję "
        "wykonał użytkownik w każdym kroku.\n\n"
        f"Ekrany:\n{screens_block}\n\n"
        f"Wykryte przejścia:\n{steps_block}\n\n"
        "Zwróć WYŁĄCZNIE obiekt JSON mapujący numer kroku na opis akcji, np.:\n"
        '{"1": "Użytkownik kliknął przycisk Zaloguj", "2": "Użytkownik wypełnił pole Email"}'
    )


def parse_flow_response(content: str) -> dict[int, str]:
    """Parse the LLM JSON response into ``{sequence: description}``.

    Tolerates surrounding prose / markdown fences by extracting the first JSON
    object. Returns an empty mapping when nothing parseable is found.
    """
    if not content:
        return {}
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {}
    try:
        raw = json.loads(match.group(0))
    except (ValueError, TypeError):
        return {}

    out: dict[int, str] = {}
    for key, value in raw.items():
        try:
            seq = int(key)
        except (ValueError, TypeError):
            continue
        if isinstance(value, str) and value.strip():
            out[seq] = value.strip()
    return out
