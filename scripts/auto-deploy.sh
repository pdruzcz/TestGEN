#!/usr/bin/env bash
# TestGEN — Auto-deploy via git polling
# Called by cron every minute
set -euo pipefail

PROJECT_DIR="/home/gen/testgen"
LOCK_FILE="$PROJECT_DIR/.deploy.lock"
LOG_FILE="$PROJECT_DIR/deploy.log"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(($(date +%s) - $(date +%s -r "$LOCK_FILE")))
    if [ "$LOCK_AGE" -lt 300 ]; then
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi

touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$PROJECT_DIR"

# Check for new commits
git fetch origin main 2>/dev/null
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== New commit detected: $REMOTE ==="

# Pull
log "Pulling..."
git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE"

# Build
log "Building..."
docker compose build --parallel 2>&1 | tail -5 | tee -a "$LOG_FILE"

# Restart
log "Restarting..."
docker compose up -d 2>&1 | tee -a "$LOG_FILE"

# Migrate
sleep 10
log "Migrating..."
docker compose exec -T backend alembic upgrade head 2>&1 | tee -a "$LOG_FILE"

log "=== Deploy complete ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}" | tee -a "$LOG_FILE"
