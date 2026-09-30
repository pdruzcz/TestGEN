#!/usr/bin/env python
"""Ustawia ceny planów pod scenariusze sandboxa tpay (Story 7.12, §2.1 planu).

Sandbox tpay reaguje na KWOTY: grosze sterują 3DS (``*.x1`` frictionless,
``*.x3`` sukces, ``*.x5`` błąd 3DS, ``*.x6`` decline), konkretne kwoty wymuszają
błędy (karta ``500/501/503/504``; BLIK ``144/168/120/312/96/216``), zakres
``x.08-x.15`` rejestruje alias PAYID, ``495.00`` to odmowa banku bez Płatności
Powtarzalnych. Cena checkoutu pochodzi z env (``BILLING_BASIC_MONTHLY_PRICE`` /
``BILLING_PREMIUM_MONTHLY_PRICE``, §3.2a) - ten skrypt podmienia ją w pliku
``.env``; DB (``subscription_plans.price_monthly``) synchronizuje się sama
seedem przy starcie backendu.

Uruchomienie (z katalogu ``backend/``):

    python scripts/set_sandbox_prices.py --scenario frictionless
    python scripts/set_sandbox_prices.py --scenario blik_no_funds --plan premium
    python scripts/set_sandbox_prices.py --amount 30.09 --plan basic
    python scripts/set_sandbox_prices.py --reset
    python scripts/set_sandbox_prices.py --list

Po zmianie zrestartuj backend (``docker compose up -d backend`` na serwerze
testowym) i zweryfikuj: ``GET /api/v1/billing/plans`` - pole ``price_monthly``.

Uwaga: kwoty sterujące NIE są cenami produktu - to stałe pomocnicze testów
(§3.2a); po testach przywróć ``--reset`` (Basic 30.00 / Premium 50.00).
"""

import argparse
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

# backend/ w sys.path - jedno źródło prawdy stałych sterujących (fixtures 7.12)
# również przy uruchomieniu skryptu wprost (python scripts/...) i w kontenerze.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.tpay_fixtures import (
    TPAY_3DS_SUFFIXES,
    TPAY_BLIK_ERROR_AMOUNTS,
    TPAY_CARD_ERROR_AMOUNTS,
    TPAY_PAYID_AMOUNT_SUFFIXES,
)

DEFAULT_BASIC = "30.00"
DEFAULT_PREMIUM = "50.00"


def _s(suffixes: dict[str, str], key: str) -> str:
    """Grosze scenariusza 3DS jako cyfry (``x1`` -> ``01``)."""
    return suffixes[key][-1].zfill(2)


def _card(index: int) -> str:
    return TPAY_CARD_ERROR_AMOUNTS[index]


# Klucz scenariusza -> (kwota, plan docelowy, opis dla testera).
SCENARIOS: dict[str, tuple[str, str, str]] = {
    "default": (DEFAULT_BASIC, "basic", "Ceny regularne (Basic 30.00; Premium bez zmian)"),
    # Happy path (kwota neutralna - brak specjalnego zachowania sandboxa).
    "happy": (DEFAULT_BASIC, "basic", "Zakup BLIK/karta/PBL - kwota neutralna"),
    # 3DS sterowany groszami (§2.1): x1 frictionless, x3 sukces, x5 błąd, x6 decline.
    "frictionless": (f"30.{_s(TPAY_3DS_SUFFIXES, 'frictionless')}", "basic", "3DS frictionless (grosze x1)"),
    "threeds_success": (f"30.{_s(TPAY_3DS_SUFFIXES, 'success')}", "basic", "3DS sukces po challenge (grosze x3)"),
    "threeds_error": (f"30.{_s(TPAY_3DS_SUFFIXES, 'error_3ds')}", "basic", "Błąd 3DS (grosze x5)"),
    "decline": (f"30.{_s(TPAY_3DS_SUFFIXES, 'decline')}", "basic", "Decline karty (grosze x6)"),
    "challenge": ("30.02", "basic", "Ekran challenge 3DS (dowolne inne grosze)"),
    # Błędy kart/walletów (kwoty wymuszające; 504 wyłącznie dla tokena).
    "card_error_500": (_card(0), "basic", "Błąd karty/walletu (500.00)"),
    "card_error_501": (_card(1), "basic", "Błąd karty/walletu (501.00)"),
    "card_error_503": (_card(2), "basic", "Błąd karty/walletu (503.00)"),
    "card_error_504": (_card(3), "basic", "Błąd tokena karty (504.00)"),
    # Błędy BLIK (kwoty wymuszające; opłacane kodem 777xxx).
    "blik_rejected_by_payer": (
        TPAY_BLIK_ERROR_AMOUNTS["rejected_by_payer"],
        "basic",
        "BLIK odrzucony przez płatnika (144.00)",
    ),
    "blik_rejected_by_issuer": (
        TPAY_BLIK_ERROR_AMOUNTS["rejected_by_issuer"],
        "basic",
        "BLIK odrzucony przez wystawcę (168.00)",
    ),
    "blik_no_funds": (TPAY_BLIK_ERROR_AMOUNTS["insufficient_funds"], "basic", "BLIK brak środków (120.00)"),
    "blik_timeout": (TPAY_BLIK_ERROR_AMOUNTS["timeout"], "basic", "BLIK timeout (312.00)"),
    "blik_limit": (TPAY_BLIK_ERROR_AMOUNTS["limit_exceeded"], "basic", "BLIK limit (96.00)"),
    "blik_security": (TPAY_BLIK_ERROR_AMOUNTS["security"], "basic", "BLIK bezpieczeństwo (216.00)"),
    # Rejestracja aliasu PAYID (Płatności Powtarzalne) - kwoty x.08-x.15.
    "payid_alias": (
        f"30.{TPAY_PAYID_AMOUNT_SUFFIXES[0]}",
        "basic",
        "Rejestracja aliasu BLIK PAYID (x.08 z zakresu x.08-x.15)",
    ),
    # Bank płatnika bez Płatności Powtarzalnych (opis transakcji bez znaczenia
    # dla GUI - odmowa zwracana jest na create_checkout -> 422 z sugestią karty).
    "refuse_no_payid": ("495.00", "basic", "Bank bez Platnosci Powtarzalnych (refuseNoPayId -> 422)"),
}


def _env_var(plan: str) -> str:
    return "BILLING_BASIC_MONTHLY_PRICE" if plan == "basic" else "BILLING_PREMIUM_MONTHLY_PRICE"


def _validate_amount(raw: str) -> str:
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise SystemExit(f"Nieprawidłowa kwota: {raw!r} (oczekiwano np. 30.01)") from None
    if value <= 0:
        raise SystemExit(f"Kwota musi być dodatnia: {raw!r}")
    return f"{value.quantize(Decimal('0.01'))}"


def update_env_file(path: Path, var: str, amount: str) -> bool:
    """Podmienia/dodaje ``VAR=amount`` w pliku .env; zwraca True przy zmianie."""
    if not path.exists():
        raise SystemExit(f"Plik {path} nie istnieje - podaj ścieżkę przez --env-file")
    pattern = re.compile(rf"^{re.escape(var)}\s*=.*$")
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    for i, line in enumerate(lines):
        if pattern.match(line.strip()) and line.strip() != f"{var}={amount}":
            lines[i] = f"{var}={amount}"
            changed = True
            break
    else:
        lines.append(f"{var}={amount}")
        changed = True
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="Scenariusz sandboxa (patrz --list)")
    parser.add_argument("--amount", help="Kwota niestandardowa, np. 30.09 (zamiast --scenario)")
    parser.add_argument(
        "--plan",
        choices=["basic", "premium"],
        default=None,
        help="Plan, którego cenę zmieniamy (domyślnie ze scenariusza)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Ścieżka do .env (domyślnie .env w cwd; na serwerze testowym ścieżka wolumenu)",
    )
    parser.add_argument("--print-only", action="store_true", help="Nie edytuj pliku - wypisz zmienne do exportu")
    parser.add_argument("--reset", action="store_true", help="Przywróć ceny domyślne (Basic 30.00 / Premium 50.00)")
    parser.add_argument("--list", action="store_true", help="Wypisz scenariusze i kwoty")
    args = parser.parse_args()

    if args.list or not (args.scenario or args.amount or args.reset):
        print(f"{'Scenariusz':24} {'Kwota':>8}  {'Plan':7} Opis")
        for key, (amount, plan, desc) in sorted(SCENARIOS.items()):
            print(f"{key:24} {amount:>8}  {plan:7} {desc}")
        print("\nUżycie: python scripts/set_sandbox_prices.py --scenario <klucz> [--plan basic|premium]")
        return 0

    if args.reset:
        updates = [("basic", DEFAULT_BASIC, "reset ceny"), ("premium", DEFAULT_PREMIUM, "reset ceny")]
    else:
        if args.amount:
            amount = _validate_amount(args.amount)
            plan = args.plan or "basic"
            desc = "kwota niestandardowa"
        else:
            amount, plan, desc = SCENARIOS[args.scenario]
            plan = args.plan or plan
        updates = [(plan, amount, desc)]

    env_path = Path(args.env_file)
    for plan, amount, desc in updates:
        var = _env_var(plan)
        if args.print_only:
            print(f"export {var}={amount}   # {desc}")
            continue
        changed = update_env_file(env_path, var, amount)
        status = "zaktualizowano" if changed else "bez zmian"
        print(f"[{status}] {var}={amount} w {env_path}  # {desc}")

    if not args.print_only:
        print(
            "\nNastepne kroki:\n"
            "  1. Zrestartuj backend (serwer testowy):  docker compose up -d backend\n"
            "     (seed przy starcie zsynchronizuje subscription_plans.price_monthly z env)\n"
            "  2. Zweryfikuj cene:  GET /api/v1/billing/plans  ->  price_monthly\n"
            "  3. Po testach:  python scripts/set_sandbox_prices.py --reset"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
