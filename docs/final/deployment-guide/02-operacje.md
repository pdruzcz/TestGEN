# Podręcznik operacyjny — backup, skalowanie, aktualizacje, monitoring, DR

> **Wersja:** 1.0  
> **Data:** 2026-09-16  
> **Docelowy czytelnik:** inżynier DevOps / administrator systemów  
> **Dokument uzupełniający:** [01-instalacja.md](./01-instalacja.md)

---

## Spis treści

1. [Kopie zapasowe i przywracanie](#1-kopie-zapasowe-i-przywracanie)
   1. [Strategia kopii zapasowych](#11-strategia-kopii-zapasowych)
   2. [PostgreSQL — pg_dump i WAL archiving](#12-postgresql--pg_dump-i-wal-archiving)
   3. [Redis — RDB i AOF](#13-redis--rdb-i-aof)
   4. [MinIO — replikacja zasobników](#14-minio--replikacja-zasobników)
   5. [Konfiguracja i sekrety](#15-konfiguracja-i-sekrety)
   6. [Procedura przywracania](#16-procedura-przywracania)
   7. [Checklist kopii zapasowych](#17-checklist-kopii-zapasowych)
2. [Skalowanie horyzontalne](#2-skalowanie-horyzontalne)
   1. [Skalowanie workerów Celery](#21-skalowanie-workerów-celery)
   2. [Skalowanie backendu FastAPI](#22-skalowanie-backendu-fastapi)
   3. [Skalowanie PostgreSQL — repliki odczytu](#23-skalowanie-postgresql--repliki-odczytu)
   4. [Skalowanie Redis](#24-skalowanie-redis)
   5. [Automatyczne skalowanie (K8s HPA)](#25-automatyczne-skalowanie-k8s-hpa)
   6. [Tabela skalowania](#26-tabela-skalowania)
   7. [Checklist skalowania](#27-checklist-skalowania)
3. [Aktualizacje systemu](#3-aktualizacje-systemu)
   1. [Przygotowanie do aktualizacji](#31-przygotowanie-do-aktualizacji)
   2. [Aktualizacja Docker Compose](#32-aktualizacja-docker-compose)
   3. [Aktualizacja Kubernetes](#33-aktualizacja-kubernetes)
   4. [Migracje bazy danych (Alembic)](#34-migracje-bazy-danych-alembic)
   5. [Procedura wycofania zmian (rollback)](#35-procedura-wycofania-zmian-rollback)
   6. [Checklist aktualizacji](#36-checklist-aktualizacji)
4. [Monitoring](#4-monitoring)
   1. [Architektura stosu monitoringu](#41-architektura-stosu-monitoringu)
   2. [Konfiguracja Prometheus](#42-konfiguracja-prometheus)
   3. [Konfiguracja Grafana](#43-konfiguracja-grafana)
   4. [Konfiguracja Loki i Promtail](#44-konfiguracja-loki-i-promtail)
   5. [Reguły alertów](#45-reguły-alertów)
   6. [Alertmanager — routing i eskalacja](#46-alertmanager--routing-i-eskalacja)
5. [Odtwarzanie po awarii (DR)](#5-odtwarzanie-po-awarii-dr)
   1. [Strategia DR](#51-strategia-dr)
   2. [Procedura odtwarzania](#52-procedura-odtwarzania)
   3. [Ośrodek zapasowy (DR site)](#53-ośrodek-zapasowy-dr-site)
   4. [Test DR — procedura kwartalna](#54-test-dr--procedura-kwartalna)
   5. [Checklist DR](#55-checklist-dr)

---

## Format procedur

Każda procedura jest opisana według schematu:

| Element | Opis |
|---------|------|
| **Cel** | co procedura realizuje |
| **Wymagania wstępne** | co musi być spełnione przed rozpoczęciem |
| **Kroki** | numerowana lista poleceń z oczekiwanymi wynikami |
| **Weryfikacja** | jak potwierdzić poprawność wykonania |
| **Czas wykonania** | szacowany czas |
| **Checklist** | lista kontrolna do odznaczenia |

---

## 1. Kopie zapasowe i przywracanie

### 1.1. Strategia kopii zapasowych

| Parametr | Wartość | Źródło |
|----------|---------|--------|
| RPO (maksymalna utrata danych) | < 1 godzina | NFR32 |
| RTO (maksymalny czas przywracania) | < 4 godziny | NFR31 |
| Retencja kopii dziennych | 30 dni | — |
| Retencja kopii tygodniowych | 12 tygodni | — |
| Retencja kopii miesięcznych | 12 miesięcy | — |

**Harmonogram:**

| Komponent | Typ kopii | Częstotliwość | Metoda |
|-----------|-----------|---------------|--------|
| PostgreSQL | pełna (pg_dump) | codziennie 02:00 | skrypt + cron |
| PostgreSQL | ciągła (WAL) | ciągle | archive_command |
| Redis | migawka (RDB) | co 15 min / co 5 min | konfiguracja save |
| Redis | dziennik (AOF) | ciągle | appendfsync everysec |
| MinIO | replikacja | codziennie 03:00 | mc mirror |
| Konfiguracja | pełna | po każdej zmianie | skrypt + git |

**Miejsce docelowe kopii:**

- Magazyn zdalny (S3-compatible, NFS, lub drugi serwer)
- :warning: **Nigdy** nie przechowuj kopii na tym samym dysku co dane źródłowe

### 1.2. PostgreSQL — pg_dump i WAL archiving

#### Pełna kopia (pg_dump)

**Cel:** kompletna kopia bazy danych z możliwością przywrócenia na czystej instancji.

**Wymagania wstępne:** dostęp do kontenera `postgres`, katalog docelowy z wystarczającą przestrzenią.

**Kroki:**

```bash
# 1. Utworzenie katalogu na kopie
mkdir -p /backup/postgresql/daily

# 2. Wykonanie kopii w formacie custom (kompresja + selektywne przywracanie)
docker compose exec -T postgres pg_dump \
  -U testgen \
  -d testgen \
  -Fc \
  --verbose \
  > /backup/postgresql/daily/testgen_$(date +%Y%m%d_%H%M%S).dump

# 3. Sprawdzenie rozmiaru kopii
ls -lh /backup/postgresql/daily/testgen_*.dump | tail -1
```

**Weryfikacja:**

```bash
# Sprawdzenie integralności kopii
pg_restore --list /backup/postgresql/daily/testgen_XXXXXXXX_XXXXXX.dump | head -20
# Powinien wyświetlić listę obiektów (tabele, indeksy, sekwencje)
```

**Czas wykonania:** 2–15 min (zależnie od rozmiaru bazy; ~1 GB/min).

Skrypt automatyzujący: [`examples/backup-postgres.sh`](./examples/backup-postgres.sh).

#### Ciągła kopia (WAL archiving + PITR)

**Cel:** możliwość przywrócenia bazy do dowolnego punktu w czasie (RPO bliskie zeru).

**Wymagania wstępne:** `postgresql.conf` z włączonym `archive_mode` i `wal_level = replica` (patrz [01-instalacja.md, sekcja 5.2](./01-instalacja.md#52-dostrajanie-postgresqlconf)).

**Konfiguracja:**

```ini
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /backup/postgresql/wal/%f'
archive_timeout = 300    # wymuś archiwizację co 5 min (= RPO ≤ 5 min)
```

```bash
# Utworzenie katalogu WAL
mkdir -p /backup/postgresql/wal

# Wykonanie base backup (punkt startowy PITR)
docker compose exec -T postgres pg_basebackup \
  -U testgen \
  -D /tmp/basebackup \
  --format=tar \
  --gzip \
  --checkpoint=fast \
  --label="basebackup_$(date +%Y%m%d)"

# Skopiowanie na zewnątrz kontenera
docker compose cp postgres:/tmp/basebackup /backup/postgresql/basebackup_$(date +%Y%m%d)
```

**Przywracanie PITR:**

```bash
# 1. Zatrzymanie PostgreSQL
docker compose stop postgres

# 2. Rozpakowanie base backup
rm -rf /var/lib/postgresql/data/*
tar xzf /backup/postgresql/basebackup_XXXXXXXX/base.tar.gz -C /var/lib/postgresql/data/

# 3. Konfiguracja przywracania (recovery.conf / postgresql.conf w PG16)
cat >> /var/lib/postgresql/data/postgresql.conf << 'EOF'
restore_command = 'cp /backup/postgresql/wal/%f %p'
recovery_target_time = '2026-09-16 14:30:00+02'   # punkt docelowy
recovery_target_action = promote
EOF

# 4. Utworzenie sygnału przywracania
touch /var/lib/postgresql/data/recovery.signal

# 5. Uruchomienie — PG przywróci dane do wskazanego punktu
docker compose start postgres

# 6. Weryfikacja
docker compose exec postgres psql -U testgen -c "SELECT pg_is_in_recovery();"
# Oczekiwane: false (po zakończeniu przywracania)
```

### 1.3. Redis — RDB i AOF

**Kopia RDB (migawka):**

```bash
# Ręczne wyzwolenie migawki
docker compose exec redis redis-cli BGSAVE
# Background saving started

# Sprawdzenie statusu
docker compose exec redis redis-cli LASTSAVE
# Unix timestamp ostatniej migawki

# Skopiowanie pliku RDB
docker compose cp redis:/data/dump.rdb /backup/redis/dump_$(date +%Y%m%d_%H%M%S).rdb
```

**Kopia AOF (dziennik):**

```bash
# Ręczne wymuszenie przepisania AOF
docker compose exec redis redis-cli BGREWRITEAOF

# Skopiowanie pliku AOF
docker compose cp redis:/data/appendonly.aof /backup/redis/appendonly_$(date +%Y%m%d).aof
```

**Przywracanie Redis:**

```bash
# 1. Zatrzymanie Redis
docker compose stop redis

# 2. Podmiana pliku danych
docker compose cp /backup/redis/dump_XXXXXXXX.rdb redis:/data/dump.rdb
# lub:
docker compose cp /backup/redis/appendonly_XXXXXXXX.aof redis:/data/appendonly.aof

# 3. Uruchomienie
docker compose start redis

# 4. Weryfikacja
docker compose exec redis redis-cli DBSIZE
```

**Czas wykonania:** < 1 min (RDB), < 5 min (AOF rewrite).

Skrypt automatyzujący: [`examples/backup-redis.sh`](./examples/backup-redis.sh).

### 1.4. MinIO — replikacja zasobników

**Cel:** kopia wszystkich plików przechowywanych w MinIO (kod źródłowy, dokumentacja, wyniki analiz).

```bash
# 1. Konfiguracja aliasu docelowego (zdalny serwer lub drugi MinIO)
docker compose exec minio mc alias set backup https://backup-minio.example.com \
  <BACKUP_ACCESS_KEY> <BACKUP_SECRET_KEY>

# 2. Replikacja zasobników
docker compose exec minio mc mirror local/testgen-results backup/testgen-results
docker compose exec minio mc mirror local/testgen-exports backup/testgen-exports
docker compose exec minio mc mirror local/testgen-avatars backup/testgen-avatars
# testgen-uploads — opcjonalnie (pliki usuwane po analizie, FR9)

# 3. Weryfikacja
docker compose exec minio mc ls backup/
docker compose exec minio mc du backup/testgen-results
```

**Alternatywa — kopia lokalna:**

```bash
# Kopia na dysk lokalny
mkdir -p /backup/minio
docker compose exec minio mc mirror local/testgen-results /backup/minio/testgen-results
```

**Czas wykonania:** zmienny, zależnie od ilości danych (5–60 min).

Skrypt automatyzujący: [`examples/backup-minio.sh`](./examples/backup-minio.sh).

### 1.5. Konfiguracja i sekrety

:warning: **Sekrety wymagają osobnego zabezpieczenia — szyfrowane kopie lub sejf haseł.**

```bash
# Katalog docelowy
mkdir -p /backup/config

# Pliki konfiguracyjne
cp .env /backup/config/.env_$(date +%Y%m%d)
cp docker-compose.yml /backup/config/
cp docker-compose.dev.yml /backup/config/

# Klucze JWT (krytyczne!)
cp -r backend/keys/ /backup/config/keys_$(date +%Y%m%d)/

# Certyfikaty SSL/TLS
cp /etc/ssl/certs/testgen.crt /backup/config/
cp /etc/ssl/private/testgen.key /backup/config/

# Szyfrowanie kopii (zalecane)
tar czf - /backup/config/ | \
  openssl enc -aes-256-cbc -pbkdf2 -out /backup/config_encrypted_$(date +%Y%m%d).tar.gz.enc
```

### 1.6. Procedura przywracania

**Cel:** pełne odtworzenie systemu z kopii zapasowych.

**Wymagania wstępne:** czysta maszyna z zainstalowanym Docker i Docker Compose (patrz [01-instalacja.md, sekcja 2.1](./01-instalacja.md#21-przygotowanie-systemu-operacyjnego)).

**Kroki:**

```bash
# 1. Klonowanie repozytorium
git clone https://bitbucket.org/nexio/testgen.git && cd testgen

# 2. Przywrócenie konfiguracji
cp /backup/config/.env_XXXXXXXX .env
cp -r /backup/config/keys_XXXXXXXX/ backend/keys/

# 3. Uruchomienie infrastruktury (bez backendu)
docker compose up -d postgres redis rabbitmq minio
# Czekaj na healthchecks
sleep 30

# 4. Przywrócenie PostgreSQL
docker compose exec -T postgres pg_restore \
  -U testgen -d testgen \
  --clean --if-exists \
  --no-owner --no-privileges \
  < /backup/postgresql/daily/testgen_XXXXXXXX.dump

# 5. Przywrócenie Redis (opcjonalne — dane efemeryczne)
docker compose cp /backup/redis/dump_XXXXXXXX.rdb redis:/data/dump.rdb
docker compose restart redis

# 6. Przywrócenie MinIO
docker compose exec minio mc mirror /backup/minio/testgen-results local/testgen-results
docker compose exec minio mc mirror /backup/minio/testgen-exports local/testgen-exports

# 7. Uruchomienie aplikacji
docker compose up -d

# 8. Weryfikacja
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
curl -s -o /dev/null -w "%{http_code}" http://localhost:4200
```

**Czas wykonania:** 30–120 min (zależnie od rozmiaru bazy i danych MinIO).

Skrypt automatyzujący: [`examples/restore-postgres.sh`](./examples/restore-postgres.sh).

### 1.7. Checklist kopii zapasowych

**Kopia dzienna:**

- [ ] Kopia PostgreSQL (`pg_dump`) zakończona bez błędów
- [ ] Plik kopii > 0 bajtów, integralność sprawdzona (`pg_restore --list`)
- [ ] WAL archiving działa (sprawdź opóźnienie: `SELECT pg_last_wal_replay_lsn()`)
- [ ] Migawka Redis (RDB) utworzona
- [ ] Replikacja MinIO zakończona (`mc mirror` bez błędów)
- [ ] Kopia przeniesiona na magazyn zdalny
- [ ] Usunięto kopie starsze niż retencja (30 dni / 12 tygodni / 12 miesięcy)

**Przywracanie (test miesięczny):**

- [ ] Przywrócenie PostgreSQL na instancji testowej — dane kompletne
- [ ] Przywrócenie Redis — klucze obecne
- [ ] Przywrócenie MinIO — pliki dostępne
- [ ] Aplikacja uruchamia się i odpowiada na healthcheck
- [ ] Czas przywracania < 4h (RTO)

---

## 2. Skalowanie horyzontalne

### 2.1. Skalowanie workerów Celery

**Docker Compose — dodanie workerów:**

```bash
# Uruchomienie dodatkowego workera (np. 3 instancje)
docker compose up -d --scale celery-worker=3

# Weryfikacja
docker compose ps | grep celery-worker
# celery-worker-1   Running
# celery-worker-2   Running
# celery-worker-3   Running
```

**Dostrajanie współbieżności (concurrency):**

```bash
# Zmiana concurrency per worker (domyślnie: liczba CPU)
# W docker-compose.yml lub docker-compose.override.yml:
#   command: celery -A app.workers.celery_app worker
#            --loglevel=info
#            -Q default,analysis,export,security
#            --concurrency=4

# Dla zadań intensywnych obliczeniowo (analysis) — niższa współbieżność
# Dla zadań I/O-bound (export, email) — wyższa współbieżność
```

**Dedykowane workerki per kolejka (zalecane w produkcji):**

```yaml
# docker-compose.override.yml
services:
  celery-worker-analysis:
    build:
      context: ./backend
      target: production
    command: celery -A app.workers.celery_app worker
             --loglevel=info -Q analysis --concurrency=2
    env_file: .env
    depends_on:
      rabbitmq: { condition: service_healthy }
      redis: { condition: service_healthy }

  celery-worker-default:
    build:
      context: ./backend
      target: production
    command: celery -A app.workers.celery_app worker
             --loglevel=info -Q default,export --concurrency=4
    env_file: .env
    depends_on:
      rabbitmq: { condition: service_healthy }
      redis: { condition: service_healthy }

  celery-worker-security:
    build:
      context: ./backend
      target: production
    command: celery -A app.workers.celery_app worker
             --loglevel=info -Q security --concurrency=2
    env_file: .env
    depends_on:
      rabbitmq: { condition: service_healthy }
      redis: { condition: service_healthy }
```

### 2.2. Skalowanie backendu FastAPI

**Docker Compose:**

```bash
# Uruchomienie dodatkowych replik (za reverse proxy / load balancerem)
docker compose up -d --scale backend=3
```

:warning: **Uwaga:** wbudowany healthcheck (`/api/v1/health`) działa niezależnie na każdej replice. Reverse proxy (nginx) powinien równoważyć ruch round-robin.

**Konfiguracja nginx (upstream):**

```nginx
upstream testgen-backend {
    least_conn;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    # ...
    location /api/ {
        proxy_pass http://testgen-backend;
        # ...
    }
}
```

**Kubernetes:**

```bash
kubectl scale deployment testgen-backend --replicas=4 -n testgen
kubectl get pods -l app=testgen-backend -n testgen
```

### 2.3. Skalowanie PostgreSQL — repliki odczytu

**Cel:** rozłożenie obciążenia odczytu na repliki (streaming replication).

**Konfiguracja serwera głównego (primary):**

```ini
# postgresql.conf (primary)
wal_level = replica
max_wal_senders = 5
wal_keep_size = 1GB
```

```bash
# Utworzenie użytkownika replikacji
docker compose exec postgres psql -U testgen -c "
  CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '<silne_hasło>';
"
```

```ini
# pg_hba.conf (primary) — dozwolone połączenia replikacji
host replication replicator 10.0.0.0/8 scram-sha-256
```

**Konfiguracja repliki (standby):**

```bash
# 1. Wykonanie base backup z serwera głównego
pg_basebackup -h primary-host -U replicator -D /var/lib/postgresql/data \
  --wal-method=stream --checkpoint=fast

# 2. Konfiguracja standby
cat >> /var/lib/postgresql/data/postgresql.conf << 'EOF'
primary_conninfo = 'host=primary-host port=5432 user=replicator password=<hasło>'
hot_standby = on
EOF

# 3. Sygnał standby
touch /var/lib/postgresql/data/standby.signal

# 4. Uruchomienie repliki
pg_ctl start -D /var/lib/postgresql/data
```

**Weryfikacja:**

```bash
# Na serwerze głównym
psql -U testgen -c "SELECT * FROM pg_stat_replication;"
# Powinien wyświetlić aktywną replikę

# Na replice
psql -U testgen -c "SELECT pg_is_in_recovery();"
# Oczekiwane: true
```

### 2.4. Skalowanie Redis

**Redis Sentinel (wysoka dostępność):**

```ini
# sentinel.conf
sentinel monitor testgen-redis redis-primary 6379 2
sentinel down-after-milliseconds testgen-redis 5000
sentinel failover-timeout testgen-redis 60000
sentinel parallel-syncs testgen-redis 1
sentinel auth-pass testgen-redis <hasło_redis>
```

```bash
# Uruchomienie 3 instancji Sentinel
redis-sentinel /etc/redis/sentinel.conf
```

**Redis Cluster (shardowanie):**

Zalecany dla dużej ilości danych (> 16 GB) lub bardzo wysokiej przepustowości.

```bash
# Utworzenie klastra 6-węzłowego (3 master + 3 repliki)
redis-cli --cluster create \
  redis-1:6379 redis-2:6379 redis-3:6379 \
  redis-4:6379 redis-5:6379 redis-6:6379 \
  --cluster-replicas 1

# Weryfikacja
redis-cli --cluster info redis-1:6379
```

### 2.5. Automatyczne skalowanie (K8s HPA)

Reguły skalowania zgodne z NFR22:

| Metryka | Próg skalowania w górę | Próg skalowania w dół | Komponent |
|---------|------------------------|-----------------------|-----------|
| CPU | > 70% | < 30% | backend, celery-worker |
| Pamięć | > 80% | < 40% | backend |
| Głębokość kolejki | > 100 zadań | < 10 zadań | celery-worker |

```bash
# Sprawdzenie aktualnego stanu HPA
kubectl get hpa -n testgen

# Ręczna zmiana limitów
kubectl patch hpa testgen-backend-hpa -n testgen \
  --type merge -p '{"spec":{"maxReplicas":10}}'

# Obserwacja skalowania w czasie rzeczywistym
kubectl get hpa -n testgen -w
```

Manifesty HPA zdefiniowane w [01-instalacja.md, sekcja 3.8](./01-instalacja.md#38-automatyczne-skalowanie-hpa).

### 2.6. Tabela skalowania

| Komponent | Min replik | Max replik | Metryka wyzwalająca | Uwagi |
|-----------|-----------|-----------|---------------------|-------|
| backend (FastAPI) | 2 | 8 | CPU > 70% | bezstanowy, łatwo skalowalny |
| celery-worker | 2 | 6 | CPU > 75% | dedykowane kolejki |
| celery-beat | 1 | 1 | — | **dokładnie 1** (singleton) |
| flower | 1 | 1 | — | monitoring, nie wymaga skalowania |
| frontend (nginx) | 2 | 4 | CPU > 70% | statyczne pliki, niskie zużycie |
| PostgreSQL | 1+N | 1+3 | odczyt > 80% CPU | 1 primary + N replik odczytu |
| Redis | 1 | 3 (Sentinel) | pamięć > 80% | lub Redis Cluster |
| RabbitMQ | 1 | 3 (klaster) | głębokość kolejki | quorum queues |
| MinIO | 1 | 4 (distributed) | dysk > 80% | distributed mode |

### 2.7. Checklist skalowania

- [ ] Zidentyfikowano wąskie gardło (CPU / pamięć / I/O / sieć)
- [ ] Sprawdzono metryki w Grafana przed skalowaniem
- [ ] Dodano repliki / zwiększono zasoby
- [ ] Zweryfikowano healthchecks nowych instancji
- [ ] Zweryfikowano równoważenie ruchu (load balancing)
- [ ] Zaktualizowano alerty monitoringu
- [ ] Udokumentowano zmianę w dzienniku operacyjnym

---

## 3. Aktualizacje systemu

### 3.1. Przygotowanie do aktualizacji

:warning: **Każda aktualizacja wymaga:**

1. **Kopia zapasowa** — pełna kopia PostgreSQL + konfiguracji (sekcja [1](#1-kopie-zapasowe-i-przywracanie))
2. **Okno serwisowe** — zaplanowane, skomunikowane użytkownikom
3. **Plan wycofania** — przetestowana procedura rollback
4. **Środowisko testowe** — aktualizacja najpierw na staging

**Przed rozpoczęciem:**

```bash
# 1. Wykonanie kopii zapasowej
./examples/backup-postgres.sh
./examples/backup-redis.sh
./examples/backup-minio.sh

# 2. Zanotowanie aktualnych wersji
docker compose exec backend python -c "import app; print(app.__version__)"
docker compose exec postgres psql -U testgen -c "SELECT version();"
docker compose exec backend alembic current

# 3. Pobranie nowej wersji kodu
git fetch origin
git log --oneline HEAD..origin/main | head -10
```

### 3.2. Aktualizacja Docker Compose

**Cel:** aktualizacja systemu na serwerze single-node.

**Czas wykonania:** 5–15 min (z krótką przerwą w dostępności).

```bash
# 1. Pobranie nowej wersji
cd /opt/testgen
git pull origin main

# 2. Zbudowanie nowych obrazów
docker compose build --no-cache

# 3. Zatrzymanie aplikacji (nie bazy!)
docker compose stop backend frontend celery-worker celery-beat flower

# 4. Uruchomienie z nowymi obrazami
# (migracje bazy uruchomią się automatycznie — docker-entrypoint.sh)
docker compose up -d

# 5. Śledzenie logów startu
docker compose logs -f backend --tail=50
# Szukaj: "Application startup complete"

# 6. Weryfikacja
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
docker compose ps
```

**Oczekiwane wyniki:**

- Wszystkie serwisy w stanie `healthy` / `running`
- Healthcheck zwraca `{"status": "ok"}`
- Migracje zastosowane bez błędów

### 3.3. Aktualizacja Kubernetes

#### Rolling update (domyślny)

```bash
# 1. Aktualizacja obrazów w rejestrze
docker build -t registry.example.com/testgen/backend:v2.1.0 ./backend
docker push registry.example.com/testgen/backend:v2.1.0

docker build -t registry.example.com/testgen/frontend:v2.1.0 ./frontend
docker push registry.example.com/testgen/frontend:v2.1.0

# 2. Aktualizacja Helm
helm upgrade testgen ./infrastructure/helm/testgen \
  --namespace testgen \
  --set backend.image.tag=v2.1.0 \
  --set frontend.image.tag=v2.1.0 \
  --set celeryWorker.image.tag=v2.1.0 \
  --wait --timeout 10m

# 3. Śledzenie postępu
kubectl rollout status deployment/testgen-backend -n testgen
kubectl rollout status deployment/testgen-frontend -n testgen
kubectl rollout status deployment/testgen-celery-worker -n testgen
```

#### Blue-green deployment

```bash
# 1. Wdrożenie nowej wersji jako "green"
helm install testgen-green ./infrastructure/helm/testgen \
  --namespace testgen \
  --set backend.image.tag=v2.1.0 \
  --set ingress.enabled=false

# 2. Weryfikacja "green"
kubectl port-forward -n testgen svc/testgen-green-backend 8001:8000
curl -s http://localhost:8001/api/v1/health

# 3. Przełączenie ruchu (zmiana Ingress)
kubectl patch ingress testgen-ingress -n testgen \
  --type merge -p '{"spec":{"rules":[{"host":"testgen.example.com","http":{"paths":[{"path":"/api/","pathType":"Prefix","backend":{"service":{"name":"testgen-green-backend","port":{"number":8000}}}},{"path":"/","pathType":"Prefix","backend":{"service":{"name":"testgen-green-frontend","port":{"number":80}}}}]}}]}}'

# 4. Usunięcie starej wersji (po weryfikacji)
helm uninstall testgen -n testgen
helm rename testgen-green testgen  # lub reinstall
```

#### Canary deployment

```bash
# 1. Wdrożenie canary (1 replika)
helm install testgen-canary ./infrastructure/helm/testgen \
  --namespace testgen \
  --set backend.replicaCount=1 \
  --set backend.image.tag=v2.1.0 \
  --set ingress.enabled=false

# 2. Konfiguracja podziału ruchu (nginx Ingress canary)
kubectl annotate ingress testgen-canary-ingress -n testgen \
  nginx.ingress.kubernetes.io/canary="true" \
  nginx.ingress.kubernetes.io/canary-weight="10"

# 3. Monitorowanie błędów canary (Grafana / Prometheus)
# Jeśli error rate < 1% przez 30 min → zwiększ wagę do 50% → 100%
# Jeśli error rate > 5% → rollback canary
```

### 3.4. Migracje bazy danych (Alembic)

Migracje uruchamiają się **automatycznie** przy starcie kontenera `backend`. W przypadku ręcznej kontroli:

```bash
# Sprawdzenie aktualnej rewizji
docker compose exec backend alembic current

# Sprawdzenie oczekujących migracji
docker compose exec backend alembic history --indicate-current | head -20

# Zastosowanie migracji
docker compose exec backend alembic upgrade head

# Weryfikacja
docker compose exec backend alembic current
# Powinna wyświetlić rewizję (head)
```

:warning: **Kompatybilność migracji:**

- Migracje **muszą** być kompatybilne wstecz (backward-compatible) na czas rolling update
- Unikaj: usuwania kolumn, zmiany nazw, zmiany typów w jednym kroku
- Wzorzec: dodaj nową kolumnę → migruj dane → usuń starą (w osobnych wydaniach)

### 3.5. Procedura wycofania zmian (rollback)

#### Docker Compose

```bash
# 1. Zatrzymanie serwisów
docker compose stop backend frontend celery-worker celery-beat flower

# 2. Cofnięcie kodu do poprzedniej wersji
git checkout <poprzedni_commit>

# 3. Zbudowanie i uruchomienie
docker compose build
docker compose up -d

# 4. Jeśli potrzebne — cofnięcie migracji
docker compose exec backend alembic downgrade -1

# 5. Weryfikacja
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
```

#### Kubernetes

```bash
# Rollback do poprzedniej rewizji Helm
helm rollback testgen 0 -n testgen --wait

# Lub rollback konkretnego deploymentu
kubectl rollout undo deployment/testgen-backend -n testgen

# Weryfikacja
kubectl rollout status deployment/testgen-backend -n testgen
```

**Czas wykonania:** 5–10 min (Docker Compose), 2–5 min (K8s rollback).

### 3.6. Checklist aktualizacji

**Przed aktualizacją:**

- [ ] Kopia zapasowa PostgreSQL wykonana i zweryfikowana
- [ ] Kopia konfiguracji (.env, klucze) wykonana
- [ ] Okno serwisowe zaplanowane i skomunikowane
- [ ] Changelog / release notes przeczytane
- [ ] Aktualizacja przetestowana na staging
- [ ] Plan rollback przygotowany

**W trakcie:**

- [ ] Nowe obrazy zbudowane
- [ ] Migracje zastosowane bez błędów
- [ ] Healthchecks przechodzą
- [ ] Logi bez błędów krytycznych

**Po aktualizacji:**

- [ ] Testy end-to-end przeszły (rejestracja, analiza, eksport)
- [ ] Monitoring pokazuje normalne metryki
- [ ] Użytkownicy poinformowani o zakończeniu
- [ ] Wersja udokumentowana w dzienniku operacyjnym

---

## 4. Monitoring

### 4.1. Architektura stosu monitoringu

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  Aplikacja   │────▶│  Prometheus   │────▶│  Grafana  │
│  (metryki)   │     │  (zbieranie)  │     │ (wizuali- │
└─────────────┘     └──────┬───────┘     │  zacja)   │
                           │              └─────┬─────┘
┌─────────────┐     ┌──────▼───────┐          │
│  Aplikacja   │────▶│  Promtail    │     ┌────▼──────┐
│  (logi)      │     │  (zbieranie) │────▶│   Loki    │
└─────────────┘     └──────────────┘     │  (logi)   │
                                          └─────┬─────┘
                    ┌──────────────┐           │
                    │ Alertmanager │◀──────────┘
                    │ (powiadom.)  │
                    └──────────────┘
```

| Komponent | Rola | Port domyślny |
|-----------|------|---------------|
| Prometheus | zbieranie i przechowywanie metryk | 9090 |
| Grafana | wizualizacja, dashboardy | 3000 |
| Loki | agregacja logów | 3100 |
| Promtail | agent zbierający logi | — |
| Alertmanager | routing i eskalacja alertów | 9093 |

### 4.2. Konfiguracja Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  # FastAPI (backend)
  - job_name: testgen-backend
    metrics_path: /api/v1/metrics
    static_configs:
      - targets: ["backend:8000"]

  # Celery / Flower
  - job_name: testgen-flower
    static_configs:
      - targets: ["flower:5555"]

  # PostgreSQL (wymaga postgres_exporter)
  - job_name: testgen-postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]

  # Redis (wymaga redis_exporter)
  - job_name: testgen-redis
    static_configs:
      - targets: ["redis-exporter:9121"]

  # RabbitMQ (wbudowany exporter prometheus)
  - job_name: testgen-rabbitmq
    static_configs:
      - targets: ["rabbitmq:15692"]

  # MinIO (wbudowane metryki)
  - job_name: testgen-minio
    metrics_path: /minio/v2/metrics/cluster
    static_configs:
      - targets: ["minio:9000"]

  # Node exporter (metryki systemowe)
  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]
```

**Retencja danych:**

```bash
# Uruchomienie Prometheus z retencją 90 dni
prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.retention.time=90d \
  --storage.tsdb.path=/prometheus
```

### 4.3. Konfiguracja Grafana

**Źródła danych:**

```yaml
# grafana/provisioning/datasources/datasources.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

**Dashboardy (zalecane):**

| Dashboard | Zawartość |
|-----------|----------|
| System | CPU, RAM, dysk, sieć per węzeł |
| Aplikacja | czas odpowiedzi, wskaźnik błędów, przepustowość (req/s) |
| Baza danych | aktywne połączenia, wolne zapytania, rozmiar bazy, replikacja |
| Celery / RabbitMQ | głębokość kolejek, czas przetwarzania zadań, błędy |
| MinIO | użycie dysku, ilość obiektów, przepustowość I/O |

Przykładowy dashboard: [`examples/grafana-dashboard.json`](./examples/grafana-dashboard.json).

### 4.4. Konfiguracja Loki i Promtail

**Promtail — zbieranie logów z kontenerów Docker:**

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        target_label: container
      - source_labels: ["__meta_docker_container_log_stream"]
        target_label: stream
    pipeline_stages:
      - json:
          expressions:
            level: level
            msg: message
            timestamp: timestamp
      - labels:
          level:
      - timestamp:
          source: timestamp
          format: RFC3339
```

**Przykłady zapytań LogQL:**

```logql
# Błędy backendu w ostatniej godzinie
{container="testgen-backend-1"} |= "ERROR" | json | line_format "{{.message}}"

# Wolne zapytania SQL (> 500 ms)
{container="testgen-backend-1"} |~ "slow query" | json | duration > 500ms

# Błędy Celery worker
{container=~"testgen-celery-worker.*"} |= "ERROR"

# Nieudane logowania
{container="testgen-backend-1"} |= "login_failed"
```

### 4.5. Reguły alertów

Plik: [`examples/prometheus-rules.yml`](./examples/prometheus-rules.yml).

```yaml
groups:
  - name: testgen-system
    rules:
      # Dysk > 85% (ostrzeżenie)
      - alert: DiskSpaceWarning
        expr: (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Wykorzystanie dysku > 85% na {{ $labels.instance }}"
          description: "Partycja {{ $labels.mountpoint }}: {{ $value | humanizePercentage }}"

      # Dysk > 95% (krytyczny)
      - alert: DiskSpaceCritical
        expr: (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) > 0.95
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "KRYTYCZNE: dysk > 95% na {{ $labels.instance }}"

      # CPU > 80% (ostrzeżenie)
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Wysokie zużycie CPU (> 80%) na {{ $labels.instance }}"

      # CPU > 95% (krytyczny)
      - alert: CriticalCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 95
        for: 5m
        labels:
          severity: critical

      # Pamięć > 85% (ostrzeżenie)
      - alert: HighMemoryUsage
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Wysokie zużycie pamięci (> 85%) na {{ $labels.instance }}"

  - name: testgen-application
    rules:
      # Głębokość kolejki RabbitMQ > 1000
      - alert: QueueDepthWarning
        expr: rabbitmq_queue_messages > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Kolejka {{ $labels.queue }} ma > 1000 wiadomości"

      # Wskaźnik błędów > 5%
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Wskaźnik błędów HTTP 5xx > 5%"

      # Wskaźnik błędów > 10% (krytyczny)
      - alert: CriticalErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.10
        for: 2m
        labels:
          severity: critical

      # Backend niedostępny
      - alert: BackendDown
        expr: up{job="testgen-backend"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Backend TestGEN jest niedostępny"

      # PostgreSQL niedostępny
      - alert: PostgresDown
        expr: up{job="testgen-postgres"} == 0
        for: 1m
        labels:
          severity: critical

      # Celery — brak aktywnych workerów
      - alert: NoCeleryWorkers
        expr: flower_active_workers == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Brak aktywnych workerów Celery"
```

### 4.6. Alertmanager — routing i eskalacja

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: "smtp.example.com:587"
  smtp_from: "alerts@testgen.example.com"
  smtp_auth_username: "alerts@testgen.example.com"
  smtp_auth_password: "<hasło>"
  smtp_require_tls: true

route:
  group_by: ["alertname", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: email-default

  routes:
    # Alerty krytyczne — natychmiast + Slack/PagerDuty
    - match:
        severity: critical
      receiver: critical-alerts
      repeat_interval: 1h

    # Alerty ostrzegawcze — email co 4h
    - match:
        severity: warning
      receiver: email-default
      repeat_interval: 4h

receivers:
  - name: email-default
    email_configs:
      - to: "devops@example.com"
        send_resolved: true

  - name: critical-alerts
    email_configs:
      - to: "devops-oncall@example.com"
        send_resolved: true
    # Opcjonalnie: Slack
    # slack_configs:
    #   - api_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    #     channel: "#testgen-alerts"
    #     title: '{{ .GroupLabels.alertname }}'
    #     text: '{{ .CommonAnnotations.summary }}'
```

---

## 5. Odtwarzanie po awarii (DR)

### 5.1. Strategia DR

| Parametr | Cel | Źródło |
|----------|-----|--------|
| RTO (maks. czas przywracania) | < 4 godziny | NFR31 |
| RPO (maks. utrata danych) | < 1 godzina | NFR32 |
| Częstotliwość testu DR | kwartalnie | najlepsza praktyka |
| Ośrodek zapasowy | opcjonalny (cold standby) | decyzja biznesowa |

**Priorytety przywracania (kolejność):**

1. PostgreSQL (dane krytyczne)
2. RabbitMQ (kolejki zadań)
3. Redis (cache — stratny, odbudowuje się)
4. MinIO (pliki — wyniki analiz)
5. Aplikacja (backend, frontend, Celery)

### 5.2. Procedura odtwarzania

**Cel:** przywrócenie pełnej funkcjonalności systemu po katastrofalnej awarii.

**Czas wykonania:** < 4 godziny (RTO).

| Krok | Czynność | Szacowany czas | Odpowiedzialny |
|------|----------|----------------|----------------|
| 1 | Deklaracja incydentu | 5 min | inżynier dyżurny |
| 2 | Ocena uszkodzeń | 15 min | inżynier DevOps |
| 3 | Przywracanie infrastruktury | 30–60 min | inżynier DevOps |
| 4 | Przywracanie bazy danych | 30–60 min | DBA / DevOps |
| 5 | Przywracanie magazynu (MinIO) | 15–30 min | inżynier DevOps |
| 6 | Weryfikacja systemu | 15–30 min | QA / DevOps |
| 7 | Komunikacja z użytkownikami | 5 min | PM / DevOps |
| **Łącznie** | | **~2–3.5 h** | |

**Szczegółowe kroki:**

```bash
# === KROK 1: Deklaracja incydentu ===
# Powiadomienie zespołu, utworzenie kanału incydentowego

# === KROK 2: Ocena uszkodzeń ===
# Sprawdź co działa, co nie:
docker compose ps              # lub: kubectl get pods -n testgen
docker compose logs --tail=100 # lub: kubectl logs -n testgen <pod>

# === KROK 3: Przywracanie infrastruktury ===
# A) Ten sam serwer (np. restart po awarii zasilania):
docker compose up -d

# B) Nowy serwer:
# Wykonaj kroki z 01-instalacja.md, sekcja 2.1–2.3
# Przywróć .env i klucze z kopii:
cp /backup/config/.env_XXXXXXXX .env
cp -r /backup/config/keys_XXXXXXXX/ backend/keys/

# === KROK 4: Przywracanie bazy danych ===
# Opcja A — pg_dump (RPO = czas od ostatniego backupu):
docker compose up -d postgres
sleep 15  # czekaj na healthcheck
docker compose exec -T postgres pg_restore \
  -U testgen -d testgen --clean --if-exists \
  < /backup/postgresql/daily/testgen_XXXXXXXX.dump

# Opcja B — PITR (RPO bliskie zeru):
# Patrz sekcja 1.2 — "Przywracanie PITR"

# === KROK 5: Przywracanie magazynu ===
docker compose up -d minio
sleep 15
docker compose exec minio mc mirror /backup/minio/testgen-results local/testgen-results
docker compose exec minio mc mirror /backup/minio/testgen-exports local/testgen-exports

# === KROK 6: Uruchomienie i weryfikacja ===
docker compose up -d

# Checklist weryfikacji:
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
curl -s -o /dev/null -w "%{http_code}" http://localhost:4200
docker compose exec redis redis-cli ping
docker compose exec rabbitmq rabbitmqctl status | head -5
docker compose exec minio mc admin info local

# === KROK 7: Komunikacja ===
# Powiadomienie użytkowników o przywróceniu usługi
```

### 5.3. Ośrodek zapasowy (DR site)

**Cold standby (minimalny koszt):**

- Osobna maszyna / klaster z zainstalowanym Docker / K8s
- Kopie zapasowe replikowane na magazyn zdalny (S3, NFS)
- W razie awarii: przywracanie z kopii (RTO: 2–4h)

**Warm standby (szybsze przywracanie):**

- PostgreSQL streaming replication na ośrodek zapasowy
- MinIO replikacja (`mc mirror --watch`)
- Przygotowane obrazy Docker w rejestrze
- W razie awarii: przełączenie DNS + promote repliki PG (RTO: 30–60 min)

**Replikacja danych:**

```bash
# PostgreSQL — ciągła replikacja strumieniowa
# Na ośrodku zapasowym (standby):
primary_conninfo = 'host=primary.example.com port=5432 user=replicator password=<hasło>'

# MinIO — ciągłe lustro
mc mirror --watch --overwrite local/testgen-results remote/testgen-results
```

### 5.4. Test DR — procedura kwartalna

**Cel:** potwierdzenie zdolności przywracania systemu w ramach RTO/RPO.

**Harmonogram:** co kwartał (styczeń, kwiecień, lipiec, październik).

**Procedura:**

1. **Przygotowanie** (dzień przed testem)
   - Powiadomienie zespołu
   - Przygotowanie środowiska testowego (oddzielna maszyna / przestrzeń nazw)
   - Weryfikacja dostępności kopii zapasowych

2. **Wykonanie testu**
   - Przywrócenie systemu z kopii na czystym środowisku
   - Zmierzenie czasu każdego kroku
   - Weryfikacja integralności danych

3. **Raport**
   - Czas przywracania vs. RTO
   - Utrata danych vs. RPO
   - Problemy napotkane i wnioski
   - Działania naprawcze

**Szablon raportu:**

```markdown
# Raport testu DR — Q[N] [ROK]

**Data:** [data]
**Prowadzący:** [imię nazwisko]
**Środowisko:** [opis]

## Wyniki

| Metryka | Cel | Zmierzone | Status |
|---------|-----|-----------|--------|
| RTO | < 4h | [czas] | OK / PRZEKROCZONO |
| RPO | < 1h | [czas od ostatniego backup] | OK / PRZEKROCZONO |

## Przebieg

| Krok | Opis | Czas startu | Czas końca | Status |
|------|------|-------------|------------|--------|
| 1 | Przywracanie infra | | | |
| 2 | Przywracanie PG | | | |
| 3 | Przywracanie MinIO | | | |
| 4 | Uruchomienie aplikacji | | | |
| 5 | Weryfikacja | | | |

## Problemy

1. [opis problemu i rozwiązania]

## Wnioski i działania

1. [działanie naprawcze — osoba odpowiedzialna — termin]
```

### 5.5. Checklist DR

**Gotowość (ciągła):**

- [ ] Kopie zapasowe tworzone zgodnie z harmonogramem
- [ ] Kopie przenoszone na magazyn zdalny
- [ ] Ośrodek zapasowy (jeśli warm standby) — replikacja działa
- [ ] Dokumentacja DR aktualna
- [ ] Kontakty alarmowe aktualne
- [ ] Klucze i sekrety dostępne z kopii

**Incydent DR:**

- [ ] Incydent zadeklarowany, zespół powiadomiony
- [ ] Uszkodzenia ocenione
- [ ] Infrastruktura przywrócona
- [ ] Baza danych przywrócona i zweryfikowana
- [ ] Magazyn plików przywrócony
- [ ] Aplikacja uruchomiona, healthchecks przechodzą
- [ ] Testy krytyczne (logowanie, analiza, eksport) pozytywne
- [ ] Użytkownicy poinformowani o przywróceniu usługi
- [ ] Raport post-mortem przygotowany w ciągu 48h

---

## Powiązane dokumenty

| Dokument | Opis |
|----------|------|
| [`01-instalacja.md`](./01-instalacja.md) | instalacja i konfiguracja (Story 9.6) |
| [`getting-started.md`](./getting-started.md) | szybki start dla programistów |
| [`environment-setup.md`](./environment-setup.md) | pełna lista zmiennych środowiskowych |
| [`examples/`](./examples/) | skrypty, konfiguracje, szablony |
