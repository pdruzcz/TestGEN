#!/usr/bin/env bash
# =============================================================================
# TestGEN — przywracanie PostgreSQL z kopii (pg_restore)
# =============================================================================
# Użycie: ./restore-postgres.sh /backup/postgresql/daily/testgen_XXXXXXXX.dump
# =============================================================================

set -euo pipefail

# --- Sprawdzenie argumentu ---
if [ $# -lt 1 ]; then
  echo "Użycie: $0 <ścieżka_do_pliku_dump>" >&2
  echo "Przykład: $0 /backup/postgresql/daily/testgen_20260916_020000.dump" >&2
  exit 1
fi

DUMP_FILE="$1"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/testgen}"
DB_USER="${POSTGRES_USER:-testgen}"
DB_NAME="${POSTGRES_DB:-testgen}"

# --- Walidacja ---
if [ ! -f "${DUMP_FILE}" ]; then
  echo "BŁĄD: Plik ${DUMP_FILE} nie istnieje" >&2
  exit 1
fi

if ! pg_restore --list "${DUMP_FILE}" > /dev/null 2>&1; then
  echo "BŁĄD: Plik ${DUMP_FILE} nie jest poprawną kopią pg_dump" >&2
  exit 1
fi

cd "${COMPOSE_DIR}"

echo "============================================="
echo " PRZYWRACANIE BAZY DANYCH PostgreSQL"
echo "============================================="
echo " Plik:  ${DUMP_FILE}"
echo " Baza:  ${DB_NAME}"
echo " Użyt.: ${DB_USER}"
echo "============================================="
echo ""
echo "UWAGA: Ta operacja NADPISZE istniejące dane w bazie ${DB_NAME}!"
read -rp "Kontynuować? (tak/nie): " CONFIRM

if [ "${CONFIRM}" != "tak" ]; then
  echo "Anulowano."
  exit 0
fi

echo ""
echo "[$(date)] Sprawdzanie dostępności PostgreSQL..."
docker compose exec -T postgres pg_isready -U "${DB_USER}" || {
  echo "BŁĄD: PostgreSQL nie odpowiada. Uruchom: docker compose up -d postgres" >&2
  exit 1
}

echo "[$(date)] Zatrzymywanie aplikacji (backend, celery)..."
docker compose stop backend celery-worker celery-beat flower 2>/dev/null || true

echo "[$(date)] Przywracanie bazy danych..."
docker compose exec -T postgres pg_restore \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --verbose \
  < "${DUMP_FILE}" 2>/tmp/pg_restore_stderr.log

RESTORE_EXIT=$?

if [ ${RESTORE_EXIT} -ne 0 ]; then
  echo "[$(date)] OSTRZEŻENIE: pg_restore zakończył się z kodem ${RESTORE_EXIT}" >&2
  echo "  Niektóre ostrzeżenia są normalne (np. 'relation does not exist' przy --clean)." >&2
  echo "  Sprawdź logi: /tmp/pg_restore_stderr.log" >&2
fi

echo "[$(date)] Uruchamianie aplikacji..."
docker compose up -d

echo "[$(date)] Oczekiwanie na healthchecks (30 s)..."
sleep 30

echo "[$(date)] Weryfikacja..."

# Sprawdzenie healthcheck
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null || echo "000")
if [ "${HTTP_CODE}" = "200" ]; then
  echo "[$(date)] Backend: OK (HTTP ${HTTP_CODE})"
else
  echo "[$(date)] Backend: BŁĄD (HTTP ${HTTP_CODE})" >&2
fi

# Sprawdzenie liczby tabel
TABLE_COUNT=$(docker compose exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
echo "[$(date)] Liczba tabel w bazie: ${TABLE_COUNT}"

echo ""
echo "============================================="
echo " Przywracanie zakończone."
echo "============================================="
