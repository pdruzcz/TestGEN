"""Shared constants used across the application."""

# Nil UUID used for RLS context in unauthenticated flows and admin bypass.
# SET LOCAL app.current_tenant = NIL_UUID ensures RLS-protected queries
# see no tenant data (safe default for register, verify, accept flows).
NIL_UUID = "00000000-0000-0000-0000-000000000000"

# Plan quotas (per PRD NFR24)
PROJECT_LIMIT_BASIC = 10
# Professional plan has no project limit
