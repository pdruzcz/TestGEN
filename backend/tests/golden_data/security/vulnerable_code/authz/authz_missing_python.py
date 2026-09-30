# Golden security fixture (Story 4.14) — missing authorization (CWE-862).
# Intentionally vulnerable reference sample for scanner regression tests.

from rest_framework.permissions import AllowAny


class AdminViewSet:
    permission_classes = [AllowAny]

    def destroy(self, request, pk):
        return delete_account(pk)
