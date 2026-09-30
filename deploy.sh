#!/usr/bin/env bash
# ==============================================================================
# TestGEN — deployment na środowisko klienckie
# ==============================================================================
# Wymagania: Docker 24+, Docker Compose v2+, Git, curl, openssl
# Użycie:    bash deploy.sh
# Domena:    domyślnie test-gen.pl; inna: TESTGEN_DOMAIN=example.pl bash deploy.sh
#
# Skrypt jest ŚRODOWISKOWO-NEUTRALNY i bez sekretów (bezpieczny w repo):
# - hasła infrastruktury generuje losowo do .env (pierwsze uruchomienie),
# - sekrety usług zewnętrznych (skrzynka M365, tpay client_secret/security
#   code, hasło admina-pierwszego) zostają PLACEHOLDERAMI w .env —
#   uzupełniasz je ręcznie przy stawianiu (patrz podsumowanie na końcu).
# ==============================================================================

set -euo pipefail

# ── Kolory ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ── Konfiguracja ──────────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
KEYS_DIR="$PROJECT_DIR/backend/keys"

DOMAIN="${TESTGEN_DOMAIN:-test-gen.pl}"
APP_URL="https://${DOMAIN}"

# ==============================================================================
# 1. Weryfikacja środowiska
# ==============================================================================
info "Środowisko docelowe: ${APP_URL} (TESTGEN_DOMAIN nadpisuje domenę)"

info "Sprawdzam wymagane narzędzia..."

command -v docker >/dev/null 2>&1   || fail "Docker nie jest zainstalowany"
command -v docker >/dev/null 2>&1   && ok "Docker $(docker --version | grep -oP '\d+\.\d+\.\d+')"
command -v git >/dev/null 2>&1      || fail "Git nie jest zainstalowany"
command -v git >/dev/null 2>&1      && ok "Git $(git --version | grep -oP '\d+\.\d+\.\d+')"
command -v curl >/dev/null 2>&1     || fail "curl nie jest zainstalowany"
command -v openssl >/dev/null 2>&1  || fail "openssl nie jest zainstalowany"

docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 nie jest dostępny"
ok "Docker Compose $(docker compose version --short)"

docker info >/dev/null 2>&1 || fail "Docker daemon nie odpowiada — sprawdź: systemctl start docker"
ok "Docker daemon działa"

echo ""

# ==============================================================================
# 2. Klucze RSA do JWT (RS256)
# ==============================================================================
if [ -f "$KEYS_DIR/private.pem" ] && [ -f "$KEYS_DIR/public.pem" ]; then
    ok "Klucze RSA już istnieją — pomijam generowanie"
else
    info "Generuję parę kluczy RSA 4096-bit do JWT..."
    mkdir -p "$KEYS_DIR"

    openssl genpkey -algorithm RSA \
        -out "$KEYS_DIR/private.pem" \
        -pkeyopt rsa_keygen_bits:4096 \
        2>/dev/null

    openssl rsa -pubout \
        -in "$KEYS_DIR/private.pem" \
        -out "$KEYS_DIR/public.pem" \
        2>/dev/null

    chmod 600 "$KEYS_DIR/private.pem"
    chmod 644 "$KEYS_DIR/public.pem"

    ok "Klucze RSA wygenerowane w $KEYS_DIR/"
fi
echo ""

# ==============================================================================
# 3. Klucz szyfrujący do MFA (Fernet)
# ==============================================================================
info "Sprawdzam klucz szyfrujący MFA..."

ENCRYPTION_KEY=""
if [ -f "$ENV_FILE" ]; then
    ENCRYPTION_KEY=$(grep -oP '^ENCRYPTION_KEY=\K.+' "$ENV_FILE" 2>/dev/null || echo "")
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    # Fernet wymaga pełnych 44 znaków base64 (z paddingiem '=') — cryptography
    # odrzuca klucz bez paddingu, więc nie ucinamy '=' (błąd z 2026-09-28).
    ENCRYPTION_KEY=$(openssl rand 32 | base64 -w0 | sed 's/+/-/g; s/\//_/g')

    ok "Wygenerowano klucz Fernet do MFA"
else
    ok "Klucz MFA już istnieje w .env — zachowuję"
fi
echo ""

# ==============================================================================
# 4. Generowanie .env (jeśli nie istnieje)
# ==============================================================================
if [ -f "$ENV_FILE" ]; then
    warn ".env już istnieje — nie nadpisuję. Sprawdzam wymagane zmienne..."
else
    info "Tworzę plik .env dla ${APP_URL}..."

    gen_pass() {
        openssl rand -base64 32 | tr -d '=/+' | head -c 32
    }

    SECRET_KEY=$(gen_pass)
    POSTGRES_PASSWORD=$(gen_pass)
    RABBITMQ_PASSWORD=$(gen_pass)
    MINIO_PASSWORD=$(gen_pass)
    FLOWER_PASSWORD=$(gen_pass)
    ADMIN_PASSWORD=$(gen_pass)

    cat > "$ENV_FILE" << ENVEOF
# ==============================================================================
# TestGEN — Konfiguracja środowiska ${DOMAIN}
# Wygenerowano: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Hasła infrastruktury wygenerowane losowo; sekcje z placeholderami
# (EMAIL / TPAY / ADMIN) uzupełnij przy stawianiu — patrz deploy.sh.
# ==============================================================================

# ── Aplikacja ─────────────────────────────────────────────────────────────────
APP_NAME=TestGEN
APP_ENV=production
DEBUG=false
APP_URL=${APP_URL}
ENGINE_MODE=hybrid

# ── Backend ───────────────────────────────────────────────────────────────────
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
SECRET_KEY=${SECRET_KEY}

# ── JWT (RS256) ──────────────────────────────────────────────────────────────
JWT_PRIVATE_KEY_PATH=keys/private.pem
JWT_PUBLIC_KEY_PATH=keys/public.pem
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── PostgreSQL ────────────────────────────────────────────────────────────────
POSTGRES_USER=testgen
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=testgen
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://testgen:${POSTGRES_PASSWORD}@postgres:5432/testgen

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0

# ── RabbitMQ ──────────────────────────────────────────────────────────────────
RABBITMQ_USER=testgen
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672
RABBITMQ_URL=amqp://testgen:${RABBITMQ_PASSWORD}@rabbitmq:5672//

# ── MinIO ─────────────────────────────────────────────────────────────────────
MINIO_ROOT_USER=testgen
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
MINIO_ENDPOINT=minio:9000
MINIO_CONSOLE_PORT=9001
MINIO_USE_SSL=false

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL=amqp://testgen:${RABBITMQ_PASSWORD}@rabbitmq:5672//
CELERY_RESULT_BACKEND=redis://redis:6379/1

# ── Flower (monitoring Celery) ───────────────────────────────────────────────
FLOWER_USER=floweradmin
FLOWER_PASSWORD=${FLOWER_PASSWORD}

# ── Email (PLACEHOLDER — uzupełnij przy stawianiu skrzynki) ──────────────────
# Rejestracja aplikacji w Entra ID (Client Credentials) dla tej domeny.
MS_TENANT_ID=
MS_CLIENT_ID=
MS_CLIENT_SECRET=
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
EMAIL_VERIFICATION_URL_TEMPLATE=${APP_URL}/verify-email?token={token}
EMAIL_INVITATION_URL_TEMPLATE=${APP_URL}/set-password?token={token}
EMAIL_PASSWORD_RESET_URL_TEMPLATE=${APP_URL}/reset-password?token={token}

# ── tpay (płatności) ──────────────────────────────────────────────────────────
# Jawne dane merchanta — uzupełnij przy stawianiu; sekrety niżej.
TPAY_ENV=production
TPAY_CLIENT_ID=
TPAY_MERCHANT_ID=
TPAY_GROUP_ID_BLIK=150
# SEKRETY (tylko ręcznie, nigdy do repo): TPAY_CLIENT_SECRET= / TPAY_SECURITY_CODE=
TPAY_NOTIFICATION_URL=${APP_URL}/api/v1/billing/webhooks/tpay
TPAY_SUCCESS_URL=${APP_URL}/billing/checkout/success
TPAY_ERROR_URL=${APP_URL}/billing/checkout/error
TPAY_PAYMENT_METHODS_RETURN_URL=${APP_URL}/billing/payment-methods/return

# ── Cookies ──────────────────────────────────────────────────────────────────
COOKIE_SECURE=true
COOKIE_DOMAIN=${DOMAIN}

# ── MFA ──────────────────────────────────────────────────────────────────────
MFA_TOKEN_EXPIRE_MINUTES=5
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# ── Ochrona brute-force ──────────────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_MINUTES=30
LOGIN_ATTEMPTS_WINDOW_MINUTES=15

# ── Admin bootstrap ──────────────────────────────────────────────────────────
BOOTSTRAP_ADMIN=true
ADMIN_EMAIL=
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# ── Frontend ──────────────────────────────────────────────────────────────────
# Frontend stoi za nginx (kontener frontend) i proxy /api/v1 na backend —
# aplikacja i API są same-origin pod ${APP_URL}.
API_URL=${APP_URL}/api/v1

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS=${APP_URL}
ENVEOF

    ok ".env utworzony (hasła infrastruktury wygenerowane losowo)"
fi
echo ""

# ==============================================================================
# 5. Weryfikacja .env
# ==============================================================================
info "Sprawdzam wymagane zmienne w .env..."

# Zmienne bezwzględnie wymagane do uruchomienia usług:
REQUIRED_VARS=(
    "APP_ENV"
    "SECRET_KEY"
    "DATABASE_URL"
    "REDIS_URL"
    "RABBITMQ_URL"
    "CELERY_BROKER_URL"
    "JWT_PRIVATE_KEY_PATH"
    "JWT_PUBLIC_KEY_PATH"
    "ENCRYPTION_KEY"
    "CORS_ORIGINS"
    "COOKIE_DOMAIN"
    "TPAY_ENV"
)

# Placeholdery do uzupełnienia przy stawianiu (WARN, nie blokują):
OPTIONAL_VARS=(
    "MS_TENANT_ID"
    "MS_CLIENT_ID"
    "MS_CLIENT_SECRET"
    "SMTP_USER"
    "TPAY_CLIENT_ID"
    "TPAY_MERCHANT_ID"
    "ADMIN_EMAIL"
)

MISSING=0
for VAR in "${REQUIRED_VARS[@]}"; do
    VAL=$(grep -oP "^${VAR}=\K.+" "$ENV_FILE" 2>/dev/null || echo "")
    if [ -z "$VAL" ]; then
        warn "Brak wymaganej zmiennej: ${VAR}"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -gt 0 ]; then
    fail "Brakuje $MISSING wymaganych zmiennych w .env — popraw i uruchom ponownie"
fi
ok "Wszystkie wymagane zmienne są w .env"

PENDING=0
for VAR in "${OPTIONAL_VARS[@]}"; do
    VAL=$(grep -oP "^${VAR}=\K.+" "$ENV_FILE" 2>/dev/null || echo "")
    if [ -z "$VAL" ]; then
        warn "Do uzupełnienia przy stawianiu: ${VAR}"
        PENDING=$((PENDING + 1))
    fi
done
if [ "$PENDING" -gt 0 ]; then
    info "Placeholderów do uzupełnienia: $PENDING (aplikacja wstanie; mail/tpay/admin aktywnują się po wypełnieniu)"
else
    ok "Wszystkie opcjonalne zmienne wypełnione"
fi

CURRENT_SECRET=$(grep -oP '^SECRET_KEY=\K.+' "$ENV_FILE" 2>/dev/null || echo "")
if [ "$CURRENT_SECRET" = "change-me-in-production" ]; then
    fail "SECRET_KEY ma wartość domyślną! Zmień w .env"
fi
ok "SECRET_KEY jest ustawiony"
echo ""

# ==============================================================================
# 6. Build i uruchomienie
# ==============================================================================
info "Buduję obrazy Docker (to może potrwać kilka minut)..."

docker compose build --parallel 2>&1 | tail -5
ok "Obrazy zbudowane"
echo ""

info "Uruchamiam usługi..."
docker compose up -d
ok "Kontenery uruchomione"
echo ""

# ==============================================================================
# 7. Czekanie na healthchecki
# ==============================================================================
info "Czekam na gotowość usług (max 90s)..."

wait_for_healthy() {
    local service="$1"
    local max_attempts="${2:-18}"
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' \
            "$(docker compose ps -q "$service" 2>/dev/null)" 2>/dev/null || echo "missing")

        if [ "$STATUS" = "healthy" ]; then
            ok "$service — healthy"
            return 0
        fi

        printf "  %s — %s (próba %d/%d)\r" "$service" "$STATUS" "$attempt" "$max_attempts"
        sleep 5
        attempt=$((attempt + 1))
    done

    warn "$service — nie osiągnął healthy po $((max_attempts * 5))s"
    return 1
}

wait_for_healthy "postgres"    12
wait_for_healthy "redis"       6
wait_for_healthy "rabbitmq"    10
wait_for_healthy "minio"       10
wait_for_healthy "backend"     18
wait_for_healthy "frontend"    12
wait_for_healthy "flower"      10
echo ""

# ==============================================================================
# 8. Migracje bazy danych
# ==============================================================================
info "Uruchamiam migracje bazy danych (Alembic)..."

if docker compose exec backend alembic upgrade head 2>&1; then
    ok "Migracje wykonane pomyślnie"
else
    warn "Migracje mogły się nie powieść — sprawdź logi: docker compose logs backend"
fi
echo ""

# ==============================================================================
# 9. Podsumowanie
# ==============================================================================
echo ""
echo "============================================================"
echo -e "${GREEN}  TestGEN — deployment zakończony!${NC}"
echo "============================================================"
echo ""
echo "  Aplikacja:  ${APP_URL}"
echo "  Backend:    ${APP_URL}/api/v1/health  (proxy /api/v1 przez nginx)"
echo "  Flower:     http://<host>:5555   (floweradmin / hasło z .env)"
echo ""
echo "  Przydatne komendy:"
echo "    docker compose logs -f           — logi na żywo"
echo "    docker compose ps                — status kontenerów"
echo "    docker compose exec postgres psql -U testgen -d testgen"
echo "                                     — podgląd bazy danych"
echo "    docker compose restart backend   — restart backendu"
echo "    docker compose down              — zatrzymaj wszystko"
echo ""
echo -e "  ${YELLOW}DO ZROBIENIA PRZY STAWIANIU:${NC}"
echo "    1. TLS: ważny certyfikat dla ${DOMAIN} przed reverse-proxy"
echo "       (release-WebView i COOKIE_SECURE=true wymagają HTTPS)"
echo "    2. Skrzynka e-mail: wypełnij w .env sekcję EMAIL"
echo "       (MS_TENANT_ID/MS_CLIENT_ID/MS_CLIENT_SECRET, SMTP_USER/FROM)"
echo "    3. tpay: wypełnij TPAY_CLIENT_ID i TPAY_MERCHANT_ID (+ sekrety"
echo "       TPAY_CLIENT_SECRET/TPAY_SECURITY_CODE — nigdy do repo)"
echo "    4. Admin: ustaw ADMIN_EMAIL w .env (hasło już wygenerowane),"
echo "       potem: docker compose up -d (żeby podchwyciło bootstrap)"
echo ""
