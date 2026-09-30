# Golden security fixture (Story 4.14) — command injection (CWE-78).
# Intentionally vulnerable reference sample for scanner regression tests.

import os


def ping(host):
    os.system("ping -c 1 " + host)
