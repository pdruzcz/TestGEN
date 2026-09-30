"""Komenda ``generate`` — Story 8.10 (AC2).

Pobiera przypadki testowe ostatniej analizy i zapisuje ich kod na dysk.
Kod testu żyje na samym przypadku (`imports`, `setup_code`, `test_code`,
`teardown_code`), więc komenda nie uruchamia nic po stronie serwera — czyta
to, co analiza już wytworzyła.
"""

import re
from pathlib import Path
from typing import Any

from testgen.client import TestGENClient
from testgen.config import Config
from testgen.errors import CliError
from testgen.output import Printer

# Rozszerzenie pliku wynika z języka przypadku, nie z frameworka: ten sam
# pytest bywa zapisany jako .py, ale junit i testng dzielą .java.
EXTENSIONS: dict[str, str] = {
    "python": "py",
    "java": "java",
    "javascript": "js",
    "typescript": "ts",
    "csharp": "cs",
    "c#": "cs",
    "php": "php",
    "go": "go",
    "ruby": "rb",
}
FRAMEWORK_LANGUAGE: dict[str, str] = {
    "pytest": "python",
    "unittest": "python",
    "selenium": "python",
    "appium": "python",
    "sikulix": "python",
    "junit": "java",
    "testng": "java",
    "nunit": "csharp",
    "mstest": "csharp",
    "mocha": "javascript",
    "jest": "javascript",
    "cypress": "javascript",
    "playwright": "typescript",
    "phpunit": "php",
    "pest": "php",
}
_SAFE_NAME = re.compile(r"[^0-9a-zA-Z]+")


def run(
    client: TestGENClient,
    config: Config,
    printer: Printer,
    *,
    output_dir: Path,
    framework: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    project_id = config.require_project_id()
    chosen = framework or config.default_framework
    if not chosen:
        raise CliError(
            "Nie wskazano frameworka",
            hint="Podaj --framework albo ustaw `default_framework` w .testgen.yaml",
        )

    printer.info(f"Pobieram przypadki testowe ({chosen})…")
    payload = client.list_test_cases(project_id, framework=chosen)
    cases = payload.get("items") or []
    if not cases:
        raise CliError(
            f"Brak przypadków testowych dla frameworka {chosen}",
            hint="Uruchom najpierw `testgen analyze --wait`.",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped = 0
    for case in cases:
        code = render_test_file(case)
        if not code:
            # Przypadek opisowy (manualny) nie ma kodu — pominięcie jest
            # normalne, ale liczymy je, żeby użytkownik nie szukał braków.
            skipped += 1
            continue
        target = output_dir / file_name(case, chosen, language)
        target.write_text(code, encoding="utf-8")
        written.append(str(target))

    result = {
        "project_id": project_id,
        "framework": chosen,
        "output_dir": str(output_dir),
        "files_written": len(written),
        "skipped_without_code": skipped,
        "files": written,
    }
    printer.result(result)
    printer.success(f"Zapisano {len(written)} plików do {output_dir}")
    if skipped:
        printer.warning(f"Pominięto {skipped} przypadków bez kodu testowego")
    return result


def render_test_file(case: dict[str, Any]) -> str:
    """Skleja fragmenty przypadku w jeden plik. Pusty wynik = brak kodu."""
    body = (case.get("test_code") or "").strip()
    if not body:
        return ""
    parts = [
        (case.get("imports") or "").strip(),
        (case.get("setup_code") or "").strip(),
        body,
        (case.get("teardown_code") or "").strip(),
    ]
    return "\n\n".join(part for part in parts if part) + "\n"


def file_name(case: dict[str, Any], framework: str, language: str | None) -> str:
    lang = (language or case.get("language") or FRAMEWORK_LANGUAGE.get(framework) or "").lower()
    extension = EXTENSIONS.get(lang, "txt")
    slug = _SAFE_NAME.sub("_", str(case.get("title") or "test")).strip("_").lower() or "test"
    # Identyfikator w nazwie: tytuły przypadków bywają identyczne, a nadpisany
    # plik zniknąłby bez śladu.
    short_id = str(case.get("id") or "")[:8]
    prefix = "" if slug.startswith("test") else "test_"
    return f"{prefix}{slug}_{short_id}.{extension}" if short_id else f"{prefix}{slug}.{extension}"
