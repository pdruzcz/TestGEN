"""Unit tests — dane wystawcy na fakturze (Story 7.6 + uzupełnienie 2026-09-22).

Wystawca (TestGEN Sp. z o.o.) musi nieść NIP/KRS/REGON i adres siedziby:
config → ``seller_snapshot`` → kolumny snapshot ``Invoice`` → kontekst
PDF → template. Env nie powinien musieć nic ustawiać — realne dane są
defaultami configu (nadpisywalne, jak dotąd, przez ``INVOICE_SELLER_*``).
"""

from app.core.config_billing import BillingSettings
from app.models.invoice import Invoice
from app.services.billing.invoice_service import InvoiceService, seller_snapshot

COMPANY = {
    "nip": "7394004057",
    "krs": "0001118599",
    "regon": "529240482",
    "street": "ul. Karola Brzostowskiego 10A / 4",
    "city": "Augustów",
    "postal_code": "16-300",
}


class TestConfigDefaults:
    def test_defaults_carry_company_registry_data(self):
        """Realne dane firmy są defaultami — deploy działa bez env."""
        s = BillingSettings(_env_file=None)
        assert s.invoice_seller_nip == COMPANY["nip"]
        assert s.invoice_seller_krs == COMPANY["krs"]
        assert s.invoice_seller_regon == COMPANY["regon"]
        assert s.invoice_seller_address["street"] == COMPANY["street"]
        assert s.invoice_seller_address["city"] == COMPANY["city"]
        assert s.invoice_seller_address["postal_code"] == COMPANY["postal_code"]
        assert s.invoice_seller_address["country"] == "Polska"


class TestSellerSnapshot:
    def test_snapshot_contains_registry_data(self, monkeypatch):
        billing = BillingSettings(_env_file=None)
        monkeypatch.setattr(
            "app.services.billing.invoice_service.get_billing_settings",
            lambda: billing,
        )
        snap = seller_snapshot()
        assert snap["nip"] == COMPANY["nip"]
        assert snap["krs"] == COMPANY["krs"]
        assert snap["regon"] == COMPANY["regon"]
        assert snap["address"]["street"] == COMPANY["street"]
        assert snap["address"]["city"] == COMPANY["city"]
        assert snap["address"]["postal_code"] == COMPANY["postal_code"]


def _invoice(**seller_overrides) -> Invoice:
    base = {
        "invoice_number": "FV/2026/09/0001",
        "seller_name": "TestGEN Sp. z o.o.",
        "seller_nip": COMPANY["nip"],
        "seller_krs": COMPANY["krs"],
        "seller_regon": COMPANY["regon"],
        "seller_address": {
            "street": COMPANY["street"],
            "city": COMPANY["city"],
            "postal_code": COMPANY["postal_code"],
            "country": "Polska",
        },
    }
    base.update(seller_overrides)
    from datetime import date

    return Invoice(
        tenant_id=None,
        issue_date=date(2026, 9, 22),
        sale_date=date(2026, 9, 22),
        **base,
        buyer_name="Nabywca",
        buyer_nip="1234567890",
        buyer_address={"street": "ul. X 1", "city": "Warszawa", "postal_code": "00-001", "country": "Polska"},
        items=[
            {
                "name": "Plan Basic",
                "period": "wrzesień 2026",
                "net": "24.39",
                "vat_rate": "0.23",
                "vat_amount": "5.61",
                "gross": "30.00",
            }
        ],
        subtotal_net=2439,
        vat_rate="0.23",
        vat_amount=561,
        total_gross=3000,
        currency="PLN",
    )


class TestTemplateContext:
    def test_context_passes_krs_and_regon(self):
        ctx = InvoiceService(db=None)._template_context(_invoice())
        assert ctx["seller"]["nip"] == COMPANY["nip"]
        assert ctx["seller"]["krs"] == COMPANY["krs"]
        assert ctx["seller"]["regon"] == COMPANY["regon"]
        assert ctx["seller"]["address"]["street"] == COMPANY["street"]

    def test_context_missing_krs_falls_back_to_empty(self):
        ctx = InvoiceService(db=None)._template_context(_invoice(seller_krs=None, seller_regon=None))
        assert ctx["seller"]["krs"] == ""
        assert ctx["seller"]["regon"] == ""


class TestTemplateRendering:
    def _render(self, seller: dict) -> str:
        from app.services.billing.invoice_service import _jinja_env

        ctx = InvoiceService(db=None)._template_context(_invoice())
        ctx["seller"] = seller
        return _jinja_env.get_template("invoice_template.html").render(**ctx)

    def test_render_shows_krs_and_regon(self):
        html = self._render(
            {
                "name": "TestGEN Sp. z o.o.",
                "nip": COMPANY["nip"],
                "krs": COMPANY["krs"],
                "regon": COMPANY["regon"],
                "address": {
                    "street": COMPANY["street"],
                    "city": COMPANY["city"],
                    "postal_code": COMPANY["postal_code"],
                    "country": "Polska",
                },
            }
        )
        assert f"KRS: {COMPANY['krs']}" in html
        assert f"REGON: {COMPANY['regon']}" in html
        assert f"NIP: {COMPANY['nip']}" in html
        assert COMPANY["street"] in html
        assert "16-300 Augustów" in html

    def test_render_hides_missing_krs_regon(self):
        html = self._render(
            {
                "name": "TestGEN Sp. z o.o.",
                "nip": "1111111111",
                "krs": "",
                "regon": "",
                "address": {"street": "ul. Y 2", "city": "Gdańsk", "postal_code": "80-001", "country": "Polska"},
            }
        )
        assert "KRS:" not in html
        assert "REGON:" not in html
