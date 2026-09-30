#!/usr/bin/env bash
# =============================================================================
# TestGEN — kopia zapasowa MinIO (mc mirror)
# =============================================================================
# Użycie: ./backup-minio.sh
# Cron:   0 3 * * * /opt/testgen/docs/final/deployment-guide/examples/backup-minio.sh
# =============================================================================

set -euo pipefail

# --- Konfiguracja ---
BACKUP_DIR="${BACKUP_DIR:-/backup/minio}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/testgen}"
BUCKETS="testgen-results testgen-exports testgen-avatars"

# --- Przygotowanie ---
mkdir -p "${BACKUP_DIR}"
cd "${COMPOSE_DIR}"

echo "[$(date)] Rozpoczęcie kopii zapasowej MinIO..."

# --- Replikacja zasobników ---
for BUCKET in ${BUCKETS}; do
  echo "[$(date)] Replikacja zasobnika: ${BUCKET}..."
  mkdir -p "${BACKUP_DIR}/${BUCKET}"

  docker compose exec -T minio mc mirror \
    --overwrite \
    "local/${BUCKET}" \
    "/backup/minio/${BUCKET}" \
    2>/tmp/mc_mirror_${BUCKET}.log || {
      echo "[$(date)] BŁĄD: Replikacja ${BUCKET} nie powiodła się" >&2
      cat /tmp/mc_mirror_${BUCKET}.log >&2
    }

  echo "[$(date)] ${BUCKET} — zakończono"
done

# --- Podsumowanie ---
echo "[$(date)] Rozmiary kopii:"
for BUCKET in ${BUCKETS}; do
  SIZE=$(du -sh "${BACKUP_DIR}/${BUCKET}" 2>/dev/null | cut -f1 || echo "brak")
  echo "  ${BUCKET}: ${SIZE}"
done

echo "[$(date)] Kopia zapasowa MinIO zakończona pomyślnie."
