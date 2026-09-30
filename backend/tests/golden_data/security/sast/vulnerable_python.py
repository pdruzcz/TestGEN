"""Golden SAST sample (Python) — known-vulnerable, Epic 4 Story 4.1.

Intentionally insecure reference code used to freeze SAST detection output.
DO NOT use any of this in production. Each flagged line is annotated below.
"""

import hashlib
import os
import pickle


def run_command(user_path):
    # command_injection (CWE-78) — os.system with concatenated input
    os.system("ls " + user_path)


def evaluate(expr):
    # code_injection (CWE-95) — eval on input
    return eval(expr)


def fetch_user(cursor, uid):
    # sql_injection (CWE-89) — f-string query
    cursor.execute(f"SELECT * FROM users WHERE id = {uid}")


def weak_digest(data):
    # weak_cryptography (CWE-327) — MD5
    return hashlib.md5(data).hexdigest()


def load_blob(blob):
    # insecure_deserialization (CWE-502) — pickle.loads
    return pickle.loads(blob)


API_KEY = "sk_live_0123456789abcdef"  # hardcoded_secret (CWE-798)
