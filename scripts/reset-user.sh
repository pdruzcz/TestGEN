#!/usr/bin/env bash
# TestGEN — Delete user + tenant for a given email so they can re-register
set -euo pipefail

EMAIL="${1:?Usage: $0 <email>}"

cd /home/gen/testgen

docker compose exec -T postgres psql -U testgen -d testgen --set ON_ERROR_STOP=1 <<SQL
BEGIN;

-- Delete email verification tokens
DELETE FROM email_verifications WHERE user_id IN (
    SELECT id FROM users WHERE email = '$EMAIL'
);

-- Delete user
DELETE FROM users WHERE email = '$EMAIL';

-- Delete orphaned tenants (no users left)
DELETE FROM tenants WHERE id NOT IN (SELECT DISTINCT tenant_id FROM users WHERE tenant_id IS NOT NULL);

COMMIT;
SQL

echo "Done — $EMAIL removed. You can now re-register."
