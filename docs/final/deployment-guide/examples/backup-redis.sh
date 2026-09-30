#!/usr/bin/env bash
# =============================================================================
# TestGEN — kopia zapasowa Redis (RDB snapshot)
# =============================================================================
# Użycie: ./backup-redis.sh
# Cron:   30 2 * * * /opt/testgen/docs/final/deployment-guide/examples/backup-redis.sh
# =============================================================================

set -euo pipefail

# --- Konfiguracja ---
BACKUP_DIR="${BACKUP_DIR:-/backup/redis}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/testgen}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# --- Przygotowanie ---
mkdir -p "${BACKUP_DIR}"
cd "${COMPOSE_DIR}"

echo "[$(date)] Rozpoczęcie kopii zapasowej Redis..."

# --- Wymuszenie zapisu RDB ---
docker compose exec -T redis redis-cli BGSAVE
echo "[$(date)] BGSAVE zlecony, oczekiwanie na zakończenie..."

# Czekaj na zakończenie zapisu (max 60 s)
for i in $(seq 1 60); do
  STATUS=$(docker compose exec -T redis redis-cli LASTSAVE)
  sleep 1
  NEW_STATUS=$(docker compose exec -T redis redis-cli LASTSAVE)
  if [ "${STATUS}" != "${NEW_STATUS}" ] || [ "${i}" -eq 1 ]; then
    break
  fi
done

# --- Skopiowanie pliku RDB ---
docker compose cp redis:/data/dump.rdb "${BACKUP_DIR}/dump_${TIMESTAMP}.rdb"

BACKUP_SIZE=$(stat -f%z "${BACKUP_DIR}/dump_${TIMESTAMP}.rdb" 2>/dev/null || stat -c%s "${BACKUP_DIR}/dump_${TIMESTAMP}.rdb" 2>/dev/null)
echo "[$(date)] Kopia utworzona: dump_${TIMESTAMP}.rdb (${BACKUP_SIZE} B)"

# --- Rotacja ---
DELETED=$(find "${BACKUP_DIR}" -name "dump_*.rdb" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
if [ "${DELETED}" -gt 0 ]; then
  echo "[$(date)] Usunięto ${DELETED} kopii starszych niż ${RETENTION_DAYS} dni"
fi

echo "[$(date)] Kopia zapasowa Redis zakończona pomyślnie."
