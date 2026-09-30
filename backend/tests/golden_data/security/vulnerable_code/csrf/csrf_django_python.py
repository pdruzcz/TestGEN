# Golden security fixture (Story 4.14) — CSRF protection disabled (CWE-352).
# Intentionally vulnerable reference sample for scanner regression tests.

from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def transfer_funds(request):
    amount = request.POST["amount"]
    return do_transfer(amount)
