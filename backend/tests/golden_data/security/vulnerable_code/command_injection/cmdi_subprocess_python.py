# Golden security fixture (Story 4.14) — command injection (CWE-78).
# Intentionally vulnerable reference sample for scanner regression tests.

import subprocess


def run(user_cmd):
    subprocess.call(user_cmd, shell=True)
