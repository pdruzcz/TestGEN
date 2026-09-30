"""Golden sample: client code with domain identifiers + secrets (Story 1.54).

Próbka celowo zawiera: nazwy zdradzające wrażliwą domenę biznesową (SSN/PESEL/
NIP/CVV/IBAN/numer konta), 4 sekrety (AWS key, token API, JWT, hasło),
URL-e, e-mail, IP oraz nazwy neutralne (invoice) — te ostatnie NIE podlegają
anonimizacji natywnej.
"""

AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
API_TOKEN = "sk-proj-99aa88bb77cc66dd"
SESSION_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0NDU1NjY3NzgifQ.k3Xx9vQmZlA0pRtY8uIoP6sDfGhJkLzX"
DB_PASSWORD = "sup3rs3cret-p4ssw0rd"


class CustomerSSNValidator:
    def validate_ssn(self, customer_ssn: str) -> bool:
        api = "https://api.premium-bank.pl/v1/ssn"
        admin = "admin@premium-bank.pl"
        node = "10.20.30.40"
        return bool(customer_ssn and api and admin and node)


class NipVerifier:
    def verify_nip(self, company_nip: str) -> bool:
        return len(company_nip) == 10


class CardCVVChecker:
    def check_cvv(self, cvv_code: str) -> bool:
        return cvv_code.isdigit()


def fetch_iban_accounts(account_number: str) -> list:
    endpoint = "https://banking.premium-bank.pl/accounts"
    return [account_number, endpoint]


def format_invoice(invoice_id: str) -> str:
    return f"FV/{invoice_id}"
