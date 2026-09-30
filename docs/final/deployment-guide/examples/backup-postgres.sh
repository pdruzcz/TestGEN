#!/usr/bin/env bash
# =============================================================================
# TestGEN — kopia zapasowa PostgreSQL (pg_dump)
# =============================================================================
# Użycie: ./backup-postgres.sh
# Cron:   0 2 * * * /opt/testgen/docs/final/deployment-guide/examples/backup-postgres.sh
# =============================================================================

set -euo pipefail

# --- Konfiguracja ---
BACKUP_DIR="${BACKUP_DIR:-/backup/postgresql/daily}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/testgen}"
DB_USER="${POSTGRES_USER:-testgen}"
DB_NAME="${POSTGRES_DB:-testgen}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/testgen_${TIMESTAMP}.dump"

# --- Przygotowanie ---
mkdir -p "${BACKUP_DIR}"
cd "${COMPOSE_DIR}"

echo "[$(date)] Rozpoczęcie kopii zapasowej PostgreSQL..."

# --- Wykonanie kopii ---
docker compose exec -T postgres pg_dump \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -Fc \
  --verbose \
  > "${BACKUP_FILE}" 2>/tmp/pg_dump_stderr.log

# --- Weryfikacja ---
BACKUP_SIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat -c%s "${BACKUP_FILE}" 2>/dev/null)

if [ "${BACKUP_SIZE}" -lt 1024 ]; then
  echo "[$(date)] BŁĄD: Kopia zbyt mała (${BACKUP_SIZE} B) — prawdopodobna awaria" >&2
  cat /tmp/pg_dump_stderr.log >&2
  rm -f "${BACKUP_FILE}"
  exit 1
fi

# Sprawdzenie integralności
if ! pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1; then
  echo "[$(date)] BŁĄD: Kopia uszkodzona — pg_restore nie może odczytać pliku" >&2
  exit 1
fi

echo "[$(date)] Kopia utworzona: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# --- Rotacja starych kopii ---
DELETED=$(find "${BACKUP_DIR}" -name "testgen_*.dump" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
if [ "${DELETED}" -gt 0 ]; then
  echo "[$(date)] Usunięto ${DELETED} kopii starszych niż ${RETENTION_DAYS} dni"
fi

echo "[$(date)] Kopia zapasowa zakończona pomyślnie."
