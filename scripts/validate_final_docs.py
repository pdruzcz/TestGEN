#!/usr/bin/env python3
"""Walidacja dokumentacji końcowej docs/final/ — Story 9.1 (Task 6).

Test konsolidacji (odpowiednik testów jednostkowych dla operacji na
Markdown):

1. Struktura — wszystkie katalogi z AC1 istnieją,
2. Linki — każdy relatywny link .md w docs/final/ wskazuje istniejący plik,
3. Native-only — zero wzmianek LLM/hybrid/dual-path/engine_mode w docs/final/,
4. Glosariusz — co najmniej 100 pozycji,
5. Raport — consolidation-report.md istnieje i mapuje wszystkie źródła
   (125 plików z docs/p1, docs/p2, docs/test-env),
6. Katalogi fazowe zniknęły (AC3 — bez duplikacji).

Użycie: python scripts/validate_final_docs.py  (exit 0 = zielono)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FINAL = REPO / "docs" / "final"

REQUIRED_DIRS = [
    "user-guide",
    "deployment-guide",
    "admin-guide",
    "architecture",
    "ai-modules",
    "troubleshooting",
    "release-notes",
]

# 125 źródeł z inwentaryzacji (Task 1, zweryfikowane stanem gita) — raport
# musi wyliczyć się co najmniej do tej liczby przetworzonych plików.
EXPECTED_SOURCE_COUNT = 125

PHASE_DIRS = [REPO / "docs" / "p1", REPO / "docs" / "p2", REPO / "docs" / "test-env"]

NATIVE_ONLY_PATTERN = re.compile(
    r"\b(LLM|llm|hybrid|dual[- ]path|engine_mode|engine mode|OpenAI|Anthropic)\b"
)

LINK_PATTERN = re.compile(r"\]\(([^)#\s]+)\.md([^)#\s]*)\)")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def check_structure() -> None:
    if not FINAL.is_dir():
        err("Brak katalogu docs/final/")
        return
    for d in REQUIRED_DIRS:
        if not (FINAL / d).is_dir():
            err(f"Brak katalogu docs/final/{d}/ (AC1)")
    for required_file in ("README.md", "consolidation-report.md", "glosariusz.md"):
        if not (FINAL / required_file).is_file():
            err(f"Brak pliku docs/final/{required_file}")


def check_links() -> None:
    if not FINAL.is_dir():
        return
    for md in sorted(FINAL.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(text):
            target = match.group(1) + ".md"
            if target.startswith(("http://", "https://", "/")):
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.is_file():
                err(f"Zerwany link: {md.relative_to(REPO)} → {target}")


def check_native_only() -> None:
    if not FINAL.is_dir():
        return
    # Meta-dokumenty konsolidacji opisują, CO zostało usunięte — muszą
    # wymieniać te terminy; poza nimi docs/final jest czysty native.
    meta_allowlist = {"inwentaryzacja-dokumentacji.md", "consolidation-report.md"}
    for md in sorted(FINAL.rglob("*.md")):
        if md.name in meta_allowlist:
            continue
        text = md.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if NATIVE_ONLY_PATTERN.search(line):
                err(
                    f"Native-only: {md.relative_to(REPO)}:{lineno} "
                    f"zawiera zabroniony termin: {line.strip()[:80]}"
                )


def check_glossary() -> None:
    path = FINAL / "glosariusz.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    rows = len(re.findall(r"^\| .+\| .+\|$", text, flags=re.MULTILINE))
    if rows < 100:
        err(f"Glosariusz: {rows} pozycji — wymaganie AC (Task 4) to ≥100")


def check_report() -> None:
    path = FINAL / "consolidation-report.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    m = re.search(r"przetworzone źródła[^\d]*(\d+)", text)
    if not m:
        # fallback: statystyki w tabeli "Razem"
        m = re.search(r"\|\s*Razem\s*\|\s*(\d+)", text)
    if not m:
        err("Raport konsolidacji: brak liczby przetworzonych źródeł")
    elif int(m.group(1)) < EXPECTED_SOURCE_COUNT:
        err(
            f"Raport konsolidacji: {m.group(1)} źródeł < {EXPECTED_SOURCE_COUNT} "
            f"(wszystkie pliki z inwentaryzacji muszą mieć decyzję)"
        )
    for stale in ("docs/p1/", "docs/p2/", "docs/test-env/"):
        # Wzmianki historyczne w kolumnie "źródło" są OK; ścieżki w kolumnie
        # "cel" muszą wskazywać docs/final — sprawdzamy tylko sekcję celów.
        targets = re.findall(r"→\s*`?([^`\n|]+)`?", text)
        bad = [t for t in targets if stale in t and "final" not in t and "(poza" not in t and " KEEP" not in t]
        if bad:
            err(f"Raport: cele wskazują stare ścieżki: {bad[:3]}")


def check_phase_dirs_gone() -> None:
    for d in PHASE_DIRS:
        if d.exists():
            err(f"Katalog fazowy nadal istnieje (AC3 — duplikacja): {d.relative_to(REPO)}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows konsole (cp1250) vs emoji/PL
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    check_structure()
    check_links()
    check_native_only()
    check_glossary()
    check_report()
    check_phase_dirs_gone()

    if warnings:
        for w in warnings:
            print(f"OSTRZEŻENIE: {w}")
    if errors:
        print(f"\n❌ Walidacja docs/final: {len(errors)} błędów\n")
        for e in errors[:60]:
            print(f"  - {e}")
        return 1
    print("✅ Walidacja docs/final: struktura, linki, native-only, glosariusz, raport — OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
