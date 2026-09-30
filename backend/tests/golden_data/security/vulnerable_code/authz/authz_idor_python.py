# Golden security fixture (Story 4.14) — IDOR (CWE-639).
# Intentionally vulnerable reference sample for scanner regression tests.


def get_invoice(request):
    return Invoice.objects.get(id=request.GET["invoice_id"])
