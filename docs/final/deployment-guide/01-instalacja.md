# Podręcznik wdrożeniowy — instalacja i konfiguracja

> **Wersja:** 1.0  
> **Data:** 2026-09-16  
> **Docelowy czytelnik:** inżynier DevOps / administrator systemów  
> **Szacowany czas wdrożenia:** < 4 h (single-node) · < 8 h (multi-node Kubernetes)

---

## Spis treści

1. [Wymagania systemowe](#1-wymagania-systemowe)
   1. [Wymagania sprzętowe](#11-wymagania-sprzętowe)
   2. [Wymagania programowe](#12-wymagania-programowe)
   3. [Wymagania sieciowe](#13-wymagania-sieciowe)
2. [Instalacja single-node (Docker Compose)](#2-instalacja-single-node-docker-compose)
   1. [Przygotowanie systemu operacyjnego](#21-przygotowanie-systemu-operacyjnego)
   2. [Pobranie i konfiguracja projektu](#22-pobranie-i-konfiguracja-projektu)
   3. [Generowanie kluczy kryptograficznych](#23-generowanie-kluczy-kryptograficznych)
   4. [Plik .env — konfiguracja zmiennych środowiskowych](#24-plik-env--konfiguracja-zmiennych-środowiskowych)
   5. [Uruchomienie systemu](#25-uruchomienie-systemu)
   6. [Inicjalizacja bazy danych i konto administratora](#26-inicjalizacja-bazy-danych-i-konto-administratora)
   7. [Weryfikacja instalacji](#27-weryfikacja-instalacji)
   8. [Rozwiązywanie problemów](#28-rozwiązywanie-problemów)
3. [Instalacja multi-node (Kubernetes)](#3-instalacja-multi-node-kubernetes)
   1. [Wymagania klastra](#31-wymagania-klastra)
   2. [Struktura Helm chart](#32-struktura-helm-chart)
   3. [Przestrzeń nazw i RBAC](#33-przestrzeń-nazw-i-rbac)
   4. [Zarządzanie sekretami](#34-zarządzanie-sekretami)
   5. [Wolumeny trwałe (PV / PVC)](#35-wolumeny-trwałe-pv--pvc)
   6. [Obiekt Ingress i routing](#36-obiekt-ingress-i-routing)
   7. [Instalacja za pomocą Helm](#37-instalacja-za-pomocą-helm)
   8. [Automatyczne skalowanie (HPA)](#38-automatyczne-skalowanie-hpa)
   9. [Weryfikacja wdrożenia](#39-weryfikacja-wdrożenia)
4. [Konfiguracja SSL/TLS](#4-konfiguracja-ssltls)
   1. [Let's Encrypt z cert-manager](#41-lets-encrypt-z-cert-manager)
   2. [Własny urząd certyfikacji (CA)](#42-własny-urząd-certyfikacji-ca)
   3. [Terminacja HTTPS](#43-terminacja-https)
5. [Konfiguracja bazy danych (PostgreSQL)](#5-konfiguracja-bazy-danych-postgresql)
   1. [Instalacja i inicjalizacja](#51-instalacja-i-inicjalizacja)
   2. [Dostrajanie postgresql.conf](#52-dostrajanie-postgresqlconf)
   3. [Row-Level Security (RLS)](#53-row-level-security-rls)
   4. [Rozszerzenia: pgcrypto i uuid-ossp](#54-rozszerzenia-pgcrypto-i-uuid-ossp)
   5. [PgBouncer — pula połączeń](#55-pgbouncer--pula-połączeń)
   6. [Migracje (Alembic)](#56-migracje-alembic)
6. [Konfiguracja Redis](#6-konfiguracja-redis)
   1. [Tryb pracy i persistence](#61-tryb-pracy-i-persistence)
   2. [Polityka eksmisji](#62-polityka-eksmisji)
   3. [Weryfikacja](#63-weryfikacja)
7. [Konfiguracja RabbitMQ](#7-konfiguracja-rabbitmq)
   1. [Kolejki i exchange](#71-kolejki-i-exchange)
   2. [Wirtualne hosty](#72-wirtualne-hosty)
   3. [Wysoka dostępność (HA)](#73-wysoka-dostępność-ha)
   4. [Weryfikacja](#74-weryfikacja)
8. [Konfiguracja MinIO / S3](#8-konfiguracja-minio--s3)
   1. [Tworzenie zasobników (buckets)](#81-tworzenie-zasobników-buckets)
   2. [Polityki dostępu](#82-polityki-dostępu)
   3. [Reguły cyklu życia](#83-reguły-cyklu-życia)
   4. [Weryfikacja](#84-weryfikacja)

---

## Konwencje dokumentu

| Element | Znaczenie |
|---------|-----------|
| `polecenie` | komenda do wykonania w terminalu |
| **pogrubienie** | wartość do dostosowania per środowisko |
| `# komentarz` | objaśnienie wewnątrz pliku konfiguracyjnego |
| :warning: | krok krytyczny — pominięcie skutkuje awarią |

Pliki konfiguracyjne przykładowe znajdują się w katalogu [`examples/`](./examples/).

---

## 1. Wymagania systemowe

### 1.1. Wymagania sprzętowe

#### Single-node (Docker Compose) — minimalne

| Komponent | vCPU | RAM | Dysk | Uwagi |
|-----------|------|-----|------|-------|
| FastAPI (backend) | 2 | 4 GB | 20 GB | serwer API + Uvicorn |
| PostgreSQL 16 | 4 | 8 GB | 100 GB SSD | baza relacyjna + RLS |
| Redis 7 | 2 | 4 GB | — | pamięć podręczna + wyniki Celery |
| RabbitMQ 3.12+ | 2 | 4 GB | — | broker zadań |
| MinIO | 2 | 4 GB | zmienny | magazyn plików (kod, dokumentacja, zrzuty) |
| Celery worker (×1) | 4 | 8 GB | — | przetwarzanie analiz |
| **Łącznie (single-node)** | **8** | **32 GB** | **200 GB SSD** | uwzgl. współdzielenie zasobów |

> **Uwaga:** wartości minimalne zakładają ≤ 5 równoczesnych analiz. Dla obciążenia produkcyjnego (> 10 równoczesnych analiz) zalecane: 16 vCPU, 64 GB RAM, NVMe SSD.

#### Multi-node (Kubernetes) — minimalne per pod

| Pod | Repliki | vCPU (request/limit) | RAM (request/limit) | Dysk (PVC) |
|-----|---------|----------------------|----------------------|------------|
| backend | 2 | 1 / 2 | 2 Gi / 4 Gi | — |
| frontend (nginx) | 2 | 0.25 / 0.5 | 256 Mi / 512 Mi | — |
| celery-worker | 2–6 | 2 / 4 | 4 Gi / 8 Gi | — |
| celery-beat | 1 | 0.25 / 0.5 | 256 Mi / 512 Mi | — |
| flower | 1 | 0.25 / 0.5 | 256 Mi / 512 Mi | — |
| PostgreSQL | 1 (lub HA) | 2 / 4 | 4 Gi / 8 Gi | 100 Gi SSD |
| Redis | 1 | 1 / 2 | 2 Gi / 4 Gi | 10 Gi |
| RabbitMQ | 1 (lub klaster) | 1 / 2 | 2 Gi / 4 Gi | 20 Gi |
| MinIO | 1 (lub distributed) | 1 / 2 | 2 Gi / 4 Gi | 500 Gi+ |

### 1.2. Wymagania programowe

| Oprogramowanie | Wersja minimalna | Uwagi |
|----------------|-----------------|-------|
| System operacyjny | AlmaLinux 9 / Ubuntu 22.04 LTS | 64-bit, jądro ≥ 5.15 |
| Docker Engine | 24.0+ | z wtyczką Compose v2 |
| Docker Compose | 2.20+ | wbudowany w Docker Desktop |
| Kubernetes | 1.28+ | tylko multi-node |
| Helm | 3.12+ | tylko multi-node |
| kubectl | zgodny z klastrem | tylko multi-node |
| Git | 2.39+ | klonowanie repozytorium |
| OpenSSL | 3.0+ | generowanie kluczy RSA |
| curl | dowolna | weryfikacja |

### 1.3. Wymagania sieciowe

#### Porty

| Port | Protokół | Usługa | Dostępność |
|------|----------|--------|------------|
| 80 | TCP | Frontend (nginx) | publiczny |
| 443 | TCP | HTTPS (reverse proxy) | publiczny |
| 8000 | TCP | Backend API (FastAPI) | wewnętrzny* |
| 5432 | TCP | PostgreSQL | wewnętrzny |
| 6379 | TCP | Redis | wewnętrzny |
| 5672 | TCP | RabbitMQ (AMQP) | wewnętrzny |
| 15672 | TCP | RabbitMQ Management | wewnętrzny |
| 9000 | TCP | MinIO API | wewnętrzny |
| 9001 | TCP | MinIO Console | wewnętrzny |
| 5555 | TCP | Flower (monitoring Celery) | wewnętrzny |

> \* W trybie single-node port 8000 jest przekierowywany przez nginx; w K8s — przez Ingress. Nie powinien być eksponowany publicznie.

#### DNS

- Domena publiczna (np. `testgen.example.com`) wskazująca na adres IP serwera / load balancera.
- Opcjonalne subdomeny: `api.testgen.example.com`, `minio.testgen.example.com`.

#### Zapora sieciowa

- Dozwolony ruch przychodzący: porty 80 i 443.
- Dozwolony ruch wychodzący: HTTPS (443) do API LLM (OpenAI, Anthropic), SMTP, tpay, Let's Encrypt.
- Komunikacja wewnętrzna: porty 5432, 6379, 5672, 9000 — wyłącznie w sieci prywatnej.

---

## 2. Instalacja single-node (Docker Compose)

### 2.1. Przygotowanie systemu operacyjnego

**AlmaLinux 9:**

```bash
# Aktualizacja pakietów
sudo dnf update -y

# Instalacja Docker Engine
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Uruchomienie i autostart
sudo systemctl enable --now docker

# Dodanie użytkownika do grupy docker
sudo usermod -aG docker $USER
newgrp docker
```

**Ubuntu 22.04 LTS:**

```bash
# Aktualizacja pakietów
sudo apt update && sudo apt upgrade -y

# Zależności
sudo apt install -y ca-certificates curl gnupg

# Klucz GPG i repozytorium Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalacja
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Użytkownik w grupie docker
sudo usermod -aG docker $USER
newgrp docker
```

**Weryfikacja:**

```bash
docker --version        # Docker version 24.x+
docker compose version  # Docker Compose version v2.20+
```

### 2.2. Pobranie i konfiguracja projektu

```bash
# Klonowanie repozytorium
git clone https://bitbucket.org/nexio/testgen.git
cd testgen

# Skopiowanie szablonu zmiennych środowiskowych
cp .env.example .env
```

### 2.3. Generowanie kluczy kryptograficznych

:warning: **Klucze RSA są wymagane do działania uwierzytelniania JWT (RS256).**

```bash
# Utworzenie katalogu na klucze
mkdir -p backend/keys

# Klucz prywatny RSA 4096-bit
openssl genrsa -out backend/keys/private.pem 4096

# Klucz publiczny
openssl rsa -in backend/keys/private.pem -pubout -out backend/keys/public.pem

# Ograniczenie uprawnień
chmod 600 backend/keys/private.pem
chmod 644 backend/keys/public.pem
```

:warning: **Klucz szyfrowania Fernet (wymagany dla MFA):**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Wynik skopiuj do ENCRYPTION_KEY w pliku .env
```

### 2.4. Plik `.env` — konfiguracja zmiennych środowiskowych

Edytuj plik `.env` i dostosuj poniższe wartości do środowiska produkcyjnego.

:warning: **Zmienne wymagające zmiany w produkcji:**

```ini
# === Tryb aplikacji ===
APP_ENV=production
DEBUG=false

# === Sekret aplikacji (losowy ciąg ≥ 64 znaki) ===
SECRET_KEY=<wygeneruj: openssl rand -hex 64>

# === Baza danych — silne hasło ===
POSTGRES_PASSWORD=<silne_hasło_min_32_znaki>
DATABASE_URL=postgresql+asyncpg://testgen:<hasło>@postgres:5432/testgen

# === Redis ===
# W produkcji zalecane zabezpieczenie hasłem:
# REDIS_URL=redis://:haslo@redis:6379/0

# === RabbitMQ — silne hasło ===
RABBITMQ_PASSWORD=<silne_hasło>
RABBITMQ_URL=amqp://testgen:<hasło>@rabbitmq:5672//

# === MinIO — silne hasło ===
MINIO_ROOT_PASSWORD=<silne_hasło_min_16_znaków>

# === Celery — adresy spójne z powyższymi ===
CELERY_BROKER_URL=amqp://testgen:<hasło_rmq>@rabbitmq:5672//
CELERY_RESULT_BACKEND=redis://redis:6379/1

# === JWT — ścieżki kluczy ===
JWT_PRIVATE_KEY_PATH=keys/private.pem
JWT_PUBLIC_KEY_PATH=keys/public.pem

# === SMTP — dane serwera pocztowego ===
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=<hasło_smtp>
SMTP_FROM_EMAIL=noreply@example.com

# === Szyfrowanie MFA ===
ENCRYPTION_KEY=<klucz_fernet_z_kroku_2.3>

# === Ciasteczka — produkcja wymaga HTTPS ===
COOKIE_SECURE=true
COOKIE_DOMAIN=testgen.example.com

# === CORS — domena produkcyjna ===
CORS_ORIGINS=https://testgen.example.com

# === URL frontendu ===
FRONTEND_BASE_URL=https://testgen.example.com
API_URL=https://testgen.example.com/api/v1

# === Flower — zmień dane logowania ===
FLOWER_USER=<użytkownik>
FLOWER_PASSWORD=<silne_hasło>

# === Konto administratora platformy ===
BOOTSTRAP_ADMIN=true
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<silne_hasło_min_12_znaków>
```

Pełna lista zmiennych: [`environment-setup.md`](./environment-setup.md).
Plik wzorcowy: [`examples/.env.production.example`](./examples/.env.production.example).

### 2.5. Uruchomienie systemu

```bash
# Zbudowanie obrazów i uruchomienie wszystkich serwisów
docker compose up -d --build

# Śledzenie logów w czasie rzeczywistym
docker compose logs -f
```

Proces budowania trwa 5–15 minut (zależnie od łącza i wydajności maszyny).

### 2.6. Inicjalizacja bazy danych i konto administratora

Migracje bazy danych uruchamiają się **automatycznie** przy starcie kontenera `backend` (skrypt `docker-entrypoint.sh` wykonuje `alembic upgrade head`).

:warning: Mechanizm blokady advisory (`pg_advisory_lock`) zapobiega wyścigowi migracji między kontenerami `backend` i `celery-worker`.

Jeśli ustawiono `BOOTSTRAP_ADMIN=true`, konto administratora platformy zostanie utworzone automatycznie przy pierwszym uruchomieniu (tenant `__system__`).

**Ręczna weryfikacja migracji:**

```bash
docker compose exec backend alembic current
# Powinno wyświetlić aktualną rewizję, np.: abc123def456 (head)

docker compose exec backend alembic history --verbose | head -20
```

### 2.7. Weryfikacja instalacji

```bash
# 1. Sprawdzenie statusu kontenerów
docker compose ps
# Wszystkie serwisy powinny mieć status "healthy" lub "running"

# 2. Healthcheck backendu
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
# Oczekiwany wynik: {"status": "ok", ...}

# 3. Sprawdzenie frontendu
curl -s -o /dev/null -w "%{http_code}" http://localhost:4200
# Oczekiwany wynik: 200

# 4. Sprawdzenie RabbitMQ Management
curl -s -u testgen:<hasło> http://localhost:15672/api/overview | python3 -m json.tool

# 5. Sprawdzenie MinIO
curl -s http://localhost:9000/minio/health/live
# Oczekiwany wynik: (pusta odpowiedź, kod 200)

# 6. Sprawdzenie Flower
curl -s -o /dev/null -w "%{http_code}" http://localhost:5555
# Oczekiwany wynik: 200 (po uwierzytelnieniu basic-auth)
```

### 2.8. Rozwiązywanie problemów

| Objaw | Prawdopodobna przyczyna | Rozwiązanie |
|-------|------------------------|-------------|
| Backend nie uruchamia się | brak kluczy RSA | Wykonaj krok [2.3](#23-generowanie-kluczy-kryptograficznych) |
| `connection refused` na porcie 5432 | PostgreSQL nie gotowy | `docker compose logs postgres` — sprawdź healthcheck |
| Migracje się nie aplikują | wyścig blokad | Sprawdź logi: `docker compose logs backend \| grep alembic` |
| Celery nie pobiera zadań | zły `RABBITMQ_URL` | Porównaj hasło w `.env` z `RABBITMQ_PASSWORD` |
| MFA rzuca błąd szyfrowania | brak `ENCRYPTION_KEY` | Wygeneruj klucz Fernet (krok [2.3](#23-generowanie-kluczy-kryptograficznych)) |
| MinIO `connection refused` | healthcheck w toku | Odczekaj 30 s; `docker compose logs minio` |
| Port zajęty | konflikt z lokalną usługą | Zmień `POSTGRES_HOST_PORT` w `.env` lub zatrzymaj kolidującą usługę |
| Brak uprawnień do pliku | `docker-entrypoint.sh` bez +x | `chmod +x backend/docker-entrypoint.sh` |

---

## 3. Instalacja multi-node (Kubernetes)

> **Uwaga:** Manifesty Kubernetes (Helm chart) zostaną dostarczone w katalogu `infrastructure/helm/testgen/`. Poniższa dokumentacja opisuje docelową architekturę wdrożenia.

### 3.1. Wymagania klastra

| Wymaganie | Minimalna wersja | Uwagi |
|-----------|-----------------|-------|
| Kubernetes | 1.28+ | zarządzany (EKS / GKE / AKS) lub bare-metal (kubeadm) |
| Helm | 3.12+ | menedżer pakietów |
| Sterownik CSI | wymagany | obsługa PersistentVolumes (np. EBS CSI, Ceph) |
| Wtyczka CNI | wymagana | Calico, Cilium lub Flannel |
| Kontroler Ingress | wymagany | nginx-ingress lub Traefik |
| cert-manager | 1.12+ | automatyzacja certyfikatów TLS |

### 3.2. Struktura Helm chart

```
infrastructure/helm/testgen/
├── Chart.yaml
├── values.yaml              # domyślna konfiguracja
├── values-production.yaml   # nadpisania produkcyjne
├── templates/
│   ├── _helpers.tpl
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment-backend.yaml
│   ├── deployment-frontend.yaml
│   ├── deployment-celery-worker.yaml
│   ├── deployment-celery-beat.yaml
│   ├── deployment-flower.yaml
│   ├── statefulset-postgres.yaml
│   ├── statefulset-redis.yaml
│   ├── statefulset-rabbitmq.yaml
│   ├── statefulset-minio.yaml
│   ├── service-backend.yaml
│   ├── service-frontend.yaml
│   ├── service-postgres.yaml
│   ├── service-redis.yaml
│   ├── service-rabbitmq.yaml
│   ├── service-minio.yaml
│   ├── ingress.yaml
│   ├── hpa-backend.yaml
│   ├── hpa-celery-worker.yaml
│   ├── pvc-postgres.yaml
│   ├── pvc-redis.yaml
│   ├── pvc-rabbitmq.yaml
│   └── pvc-minio.yaml
└── charts/                  # zależności (opcjonalne subcharty)
```

Kluczowe parametry `values.yaml` — patrz [`examples/values.yaml`](./examples/values.yaml).

### 3.3. Przestrzeń nazw i RBAC

```bash
# Utworzenie przestrzeni nazw
kubectl create namespace testgen

# Ustawienie kontekstu
kubectl config set-context --current --namespace=testgen
```

Zalecane konto serwisowe z minimalnymi uprawnieniami:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: testgen-app
  namespace: testgen
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: testgen-app-role
  namespace: testgen
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: testgen-app-binding
  namespace: testgen
subjects:
  - kind: ServiceAccount
    name: testgen-app
roleRef:
  kind: Role
  name: testgen-app-role
  apiGroup: rbac.authorization.k8s.io
```

### 3.4. Zarządzanie sekretami

:warning: **Nigdy nie przechowuj sekretów w `values.yaml` w repozytorium.**

**Opcja A — Sealed Secrets (Bitnami):**

```bash
# Instalacja kontrolera
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system

# Szyfrowanie sekretu
kubectl create secret generic testgen-secrets \
  --namespace=testgen \
  --from-literal=POSTGRES_PASSWORD='<silne_hasło>' \
  --from-literal=RABBITMQ_PASSWORD='<silne_hasło>' \
  --from-literal=MINIO_ROOT_PASSWORD='<silne_hasło>' \
  --from-literal=SECRET_KEY='<losowy_ciąg_64>' \
  --from-literal=ENCRYPTION_KEY='<klucz_fernet>' \
  --from-file=JWT_PRIVATE_KEY=backend/keys/private.pem \
  --from-file=JWT_PUBLIC_KEY=backend/keys/public.pem \
  --dry-run=client -o yaml | kubeseal -o yaml > sealed-secret.yaml

kubectl apply -f sealed-secret.yaml
```

**Opcja B — HashiCorp Vault:**

```bash
# Agent Injector — adnotacje w deployment:
# vault.hashicorp.com/agent-inject: "true"
# vault.hashicorp.com/role: "testgen"
# vault.hashicorp.com/agent-inject-secret-db: "secret/data/testgen/postgres"
```

### 3.5. Wolumeny trwałe (PV / PVC)

| Komponent | Rozmiar PVC | Klasa magazynu | Tryb dostępu |
|-----------|------------|----------------|--------------|
| PostgreSQL | 100 Gi | `ssd` (gp3 / premium-rwo) | ReadWriteOnce |
| Redis | 10 Gi | `ssd` | ReadWriteOnce |
| RabbitMQ | 20 Gi | `ssd` | ReadWriteOnce |
| MinIO | 500 Gi+ | `standard` (gp2 / standard-rwo) | ReadWriteOnce |

Przykład PVC dla PostgreSQL:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: testgen-postgres-data
  namespace: testgen
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ssd
  resources:
    requests:
      storage: 100Gi
```

### 3.6. Obiekt Ingress i routing

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: testgen-ingress
  namespace: testgen
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "500m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - testgen.example.com
      secretName: testgen-tls
  rules:
    - host: testgen.example.com
      http:
        paths:
          - path: /api/
            pathType: Prefix
            backend:
              service:
                name: testgen-backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: testgen-frontend
                port:
                  number: 80
```

### 3.7. Instalacja za pomocą Helm

```bash
# Dodanie repozytorium (jeśli chart jest hostowany)
# helm repo add testgen https://charts.example.com/testgen

# Instalacja z pliku lokalnego
helm install testgen ./infrastructure/helm/testgen \
  --namespace testgen \
  --values ./infrastructure/helm/testgen/values-production.yaml \
  --set secrets.existingSecret=testgen-secrets \
  --wait --timeout 10m

# Weryfikacja
kubectl get pods -n testgen
kubectl get svc -n testgen
kubectl get ingress -n testgen
```

### 3.8. Automatyczne skalowanie (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: testgen-backend-hpa
  namespace: testgen
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: testgen-backend
  minReplicas: 2
  maxReplicas: 8
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: testgen-celery-worker-hpa
  namespace: testgen
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: testgen-celery-worker
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 75
```

### 3.9. Weryfikacja wdrożenia

```bash
# 1. Wszystkie pody w stanie Running
kubectl get pods -n testgen
# NAME                                    READY   STATUS    RESTARTS   AGE
# testgen-backend-xxxxx                   1/1     Running   0          5m
# testgen-frontend-xxxxx                  1/1     Running   0          5m
# testgen-celery-worker-xxxxx             1/1     Running   0          5m
# testgen-celery-beat-xxxxx               1/1     Running   0          5m
# testgen-postgres-0                      1/1     Running   0          5m
# testgen-redis-0                         1/1     Running   0          5m
# testgen-rabbitmq-0                      1/1     Running   0          5m
# testgen-minio-0                         1/1     Running   0          5m

# 2. Healthcheck backendu
kubectl exec -n testgen deploy/testgen-backend -- \
  curl -sf http://localhost:8000/api/v1/health

# 3. Status Ingress
kubectl describe ingress testgen-ingress -n testgen

# 4. Certyfikat TLS
kubectl get certificate -n testgen
# NAME          READY   SECRET        AGE
# testgen-tls   True    testgen-tls   5m

# 5. Logi aplikacji
kubectl logs -n testgen deploy/testgen-backend --tail=50
kubectl logs -n testgen deploy/testgen-celery-worker --tail=50
```

---

## 4. Konfiguracja SSL/TLS

### 4.1. Let's Encrypt z cert-manager

**Instalacja cert-manager (jeśli nie zainstalowany):**

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true
```

**ClusterIssuer dla Let's Encrypt:**

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: devops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

Certyfikat jest automatycznie odnawiany 30 dni przed wygaśnięciem.

### 4.2. Własny urząd certyfikacji (CA)

Dla środowisk bez dostępu do internetu (air-gapped):

```bash
# 1. Generowanie klucza CA
openssl genrsa -out ca.key 4096

# 2. Certyfikat CA (ważność 10 lat)
openssl req -x509 -new -nodes -key ca.key -sha256 \
  -days 3650 -out ca.crt \
  -subj "/C=PL/ST=Mazowieckie/O=TestGEN/CN=TestGEN CA"

# 3. Klucz serwera
openssl genrsa -out server.key 2048

# 4. Żądanie podpisu (CSR)
openssl req -new -key server.key -out server.csr \
  -subj "/C=PL/ST=Mazowieckie/O=TestGEN/CN=testgen.example.com"

# 5. Podpisanie certyfikatu serwera
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 365 -sha256

# 6. Import do Kubernetes
kubectl create secret tls testgen-tls \
  --cert=server.crt --key=server.key \
  --namespace=testgen
```

### 4.3. Terminacja HTTPS

**Single-node — nginx jako reverse proxy:**

Utwórz plik `/etc/nginx/sites-available/testgen`:

```nginx
server {
    listen 80;
    server_name testgen.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name testgen.example.com;

    ssl_certificate     /etc/ssl/certs/testgen.crt;
    ssl_certificate_key /etc/ssl/private/testgen.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Nagłówki bezpieczeństwa
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    # Maksymalny rozmiar uploadu (500 MB dla planu Professional)
    client_max_body_size 500m;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:4200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouty dla długich analiz
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Flower (opcjonalnie — ograniczenie IP)
    location /flower/ {
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://127.0.0.1:5555/;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/testgen /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Kubernetes** — terminacja TLS realizowana jest przez Ingress (sekcja [3.6](#36-obiekt-ingress-i-routing)).

---

## 5. Konfiguracja bazy danych (PostgreSQL)

### 5.1. Instalacja i inicjalizacja

W trybie Docker Compose PostgreSQL uruchamia się automatycznie z obrazu `postgres:16-alpine`.
Konfiguracja wstępna odbywa się przez zmienne środowiskowe w pliku `.env`.

:warning: W przypadku instalacji bare-metal:

```bash
# AlmaLinux
sudo dnf install -y postgresql16-server postgresql16
sudo /usr/pgsql-16/bin/postgresql-16-setup initdb
sudo systemctl enable --now postgresql-16

# Ubuntu
sudo apt install -y postgresql-16
sudo systemctl enable --now postgresql
```

### 5.2. Dostrajanie `postgresql.conf`

Plik przykładowy: [`examples/postgresql.conf`](./examples/postgresql.conf).

Kluczowe parametry dla maszyny 8 GB RAM / 4 vCPU:

```ini
# Pamięć
shared_buffers = 2GB                 # 25% RAM
effective_cache_size = 6GB           # 75% RAM
work_mem = 64MB                      # per operacja sortowania
maintenance_work_mem = 512MB         # VACUUM, CREATE INDEX

# WAL i checkpoint
wal_buffers = 64MB
checkpoint_completion_target = 0.9
min_wal_size = 1GB
max_wal_size = 4GB

# Połączenia
max_connections = 200                # z PgBouncer: może być niższe
listen_addresses = '*'               # w Docker: 0.0.0.0

# Logowanie
log_min_duration_statement = 500     # ms — logi wolnych zapytań
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# Replikacja (przygotowanie do backup PITR)
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'
```

**Zastosowanie konfiguracji:**

```bash
# Docker Compose — podmontowanie pliku:
# volumes:
#   - ./examples/postgresql.conf:/etc/postgresql/postgresql.conf:ro
# command: postgres -c config_file=/etc/postgresql/postgresql.conf

# Weryfikacja
docker compose exec postgres psql -U testgen -c "SHOW shared_buffers;"
```

### 5.3. Row-Level Security (RLS)

TestGEN używa RLS do izolacji danych między tenantami. Polityki są tworzone automatycznie przez migracje Alembic.

**Weryfikacja:**

```bash
docker compose exec postgres psql -U testgen -d testgen -c "
  SELECT schemaname, tablename, policyname, permissive, cmd
  FROM pg_policies
  ORDER BY tablename;
"
```

Oczekiwany wynik — polityki `tenant_isolation_policy` na każdej tabeli z kolumną `tenant_id`.

**Testowanie izolacji:**

```sql
-- Ustawienie kontekstu tenanta (symulacja aplikacji)
SET app.current_tenant = 'id-tenanta-A';
SELECT * FROM projects;  -- widoczne tylko projekty tenanta A

SET app.current_tenant = 'id-tenanta-B';
SELECT * FROM projects;  -- widoczne tylko projekty tenanta B
```

### 5.4. Rozszerzenia: pgcrypto i uuid-ossp

Rozszerzenia są tworzone automatycznie przez migracje. Weryfikacja:

```bash
docker compose exec postgres psql -U testgen -d testgen -c "
  SELECT extname, extversion FROM pg_extension
  WHERE extname IN ('pgcrypto', 'uuid-ossp');
"
# Oczekiwane:
#   pgcrypto  | 1.3
#   uuid-ossp | 1.1
```

### 5.5. PgBouncer — pula połączeń

Zalecany w produkcji dla ograniczenia liczby bezpośrednich połączeń do PostgreSQL.

Plik konfiguracyjny: [`examples/pgbouncer.ini`](./examples/pgbouncer.ini).

```ini
[databases]
testgen = host=postgres port=5432 dbname=testgen

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

# Tryb puli — transaction (zalecany dla async SQLAlchemy)
pool_mode = transaction
max_client_conn = 500
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3

# Timeouty
server_idle_timeout = 300
client_idle_timeout = 600

# Logowanie
log_connections = 1
log_disconnections = 1
stats_period = 60
```

Plik `userlist.txt`:

```
"testgen" "<hasło_md5_lub_scram>"
```

Po włączeniu PgBouncer zmień `DATABASE_URL` w `.env`:

```ini
DATABASE_URL=postgresql+asyncpg://testgen:<hasło>@pgbouncer:6432/testgen
```

### 5.6. Migracje (Alembic)

Migracje uruchamiają się automatycznie przy starcie kontenera `backend` (`docker-entrypoint.sh`).

**Ręczne zarządzanie:**

```bash
# Status bieżący
docker compose exec backend alembic current

# Zastosowanie wszystkich migracji
docker compose exec backend alembic upgrade head

# Cofnięcie ostatniej migracji
docker compose exec backend alembic downgrade -1

# Historia migracji
docker compose exec backend alembic history --verbose | head -30

# Weryfikacja tabel
docker compose exec postgres psql -U testgen -d testgen -c "\dt"
```

---

## 6. Konfiguracja Redis

### 6.1. Tryb pracy i persistence

TestGEN wykorzystuje Redis do dwóch celów:
- **DB 0** — pamięć podręczna aplikacji (cache sesji, limitów)
- **DB 1** — wyniki zadań Celery (`CELERY_RESULT_BACKEND`)

Plik konfiguracyjny: [`examples/redis.conf`](./examples/redis.conf).

```ini
# Pamięć
maxmemory 4gb

# Persistence — RDB + AOF (zalecane w produkcji)
save 900 1          # zapis co 15 min jeśli ≥ 1 zmiana
save 300 10         # zapis co 5 min jeśli ≥ 10 zmian
save 60 10000       # zapis co 1 min jeśli ≥ 10000 zmian

appendonly yes
appendfsync everysec

# Bezpieczeństwo
requirepass <silne_hasło>
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG ""

# Sieć
bind 0.0.0.0
protected-mode yes
```

**Zastosowanie w Docker Compose:**

```yaml
redis:
  image: redis:7-alpine
  command: redis-server /usr/local/etc/redis/redis.conf
  volumes:
    - redis-data:/data
    - ./examples/redis.conf:/usr/local/etc/redis/redis.conf:ro
```

### 6.2. Polityka eksmisji

| Polityka | Kiedy stosować |
|----------|---------------|
| `allkeys-lru` | **zalecana** — usuwa najdawniej nieużywane klucze |
| `volatile-lru` | tylko klucze z TTL — bezpieczne, ale wymaga TTL na wszystkich kluczach |
| `noeviction` | zwraca błąd przy braku pamięci — do debugowania |

```ini
maxmemory-policy allkeys-lru
```

### 6.3. Weryfikacja

```bash
# Ping
docker compose exec redis redis-cli ping
# PONG

# Informacje o pamięci
docker compose exec redis redis-cli INFO memory | grep used_memory_human

# Informacje o persistence
docker compose exec redis redis-cli INFO persistence | grep -E "rdb_|aof_"

# Test zapisu/odczytu
docker compose exec redis redis-cli SET test "ok" EX 10
docker compose exec redis redis-cli GET test
# "ok"
```

---

## 7. Konfiguracja RabbitMQ

### 7.1. Kolejki i exchange

TestGEN wykorzystuje RabbitMQ jako broker Celery. Kolejki są tworzone automatycznie przy starcie workerów.

| Kolejka | Przeznaczenie | Priorytet |
|---------|---------------|-----------|
| `default` | zadania ogólne (email, cleanup) | normalny |
| `analysis` | analizy kodu/dokumentacji/UML/GUI | wysoki |
| `export` | eksport raportów (PDF, DOCX, CSV) | normalny |
| `security` | skanowanie bezpieczeństwa | wysoki |

Plik konfiguracyjny: [`examples/rabbitmq.conf`](./examples/rabbitmq.conf).

```ini
# Limity pamięci
vm_memory_high_watermark.relative = 0.6
vm_memory_high_watermark_paging_ratio = 0.8
disk_free_limit.relative = 1.5

# Logowanie
log.console = true
log.console.level = warning
log.file.level = info

# Management plugin (UI na porcie 15672)
management.tcp.port = 15672

# Limity połączeń
channel_max = 128
heartbeat = 60
```

### 7.2. Wirtualne hosty

Zalecana izolacja środowisk (dev / staging / produkcja) za pomocą vhostów:

```bash
# Utworzenie vhosta produkcyjnego
docker compose exec rabbitmq rabbitmqctl add_vhost /production

# Uprawnienia użytkownika
docker compose exec rabbitmq rabbitmqctl set_permissions \
  -p /production testgen ".*" ".*" ".*"
```

W `.env` zmień URL brokera:

```ini
RABBITMQ_URL=amqp://testgen:<hasło>@rabbitmq:5672/production
CELERY_BROKER_URL=amqp://testgen:<hasło>@rabbitmq:5672/production
```

### 7.3. Wysoka dostępność (HA)

Dla klastrów Kubernetes z wieloma replikami RabbitMQ:

```bash
# Polityka HA — mirroring kolejek (classic mirroring)
docker compose exec rabbitmq rabbitmqctl set_policy ha-all \
  "^" '{"ha-mode":"all","ha-sync-mode":"automatic"}' \
  --apply-to queues

# Lub w RabbitMQ 3.13+ — Quorum Queues (zalecane):
# Celery konfiguracja:
# CELERY_BROKER_TRANSPORT_OPTIONS='{"queue_arguments": {"x-queue-type": "quorum"}}'
```

### 7.4. Weryfikacja

```bash
# Status serwera
docker compose exec rabbitmq rabbitmqctl status | head -30

# Lista kolejek
docker compose exec rabbitmq rabbitmqctl list_queues \
  name messages consumers state

# Lista vhostów
docker compose exec rabbitmq rabbitmqctl list_vhosts

# Lista połączeń
docker compose exec rabbitmq rabbitmqctl list_connections \
  user vhost state

# Panel zarządzania (przeglądarka)
# http://localhost:15672  (login: testgen / hasło z .env)
```

---

## 8. Konfiguracja MinIO / S3

### 8.1. Tworzenie zasobników (buckets)

TestGEN wymaga następujących zasobników:

| Zasobnik | Przeznaczenie | Retencja |
|----------|---------------|----------|
| `testgen-uploads` | pliki źródłowe (kod, dokumentacja, UML, GUI) | usuwane po analizie (FR9) |
| `testgen-results` | wyniki analiz, raporty | długoterminowa |
| `testgen-exports` | wyeksportowane pliki (PDF, DOCX) | 30 dni |
| `testgen-avatars` | awatary użytkowników | długoterminowa |

```bash
# Instalacja klienta mc
docker compose exec minio mc alias set local http://localhost:9000 \
  ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

# Tworzenie zasobników
docker compose exec minio mc mb local/testgen-uploads
docker compose exec minio mc mb local/testgen-results
docker compose exec minio mc mb local/testgen-exports
docker compose exec minio mc mb local/testgen-avatars
```

### 8.2. Polityki dostępu

```bash
# Polityka tylko do odczytu dla zasobnika exports (dostęp publiczny do pobrania)
docker compose exec minio mc anonymous set download local/testgen-exports

# Polityka prywatna (domyślna) dla reszty
docker compose exec minio mc anonymous set none local/testgen-uploads
docker compose exec minio mc anonymous set none local/testgen-results
```

Dedykowany użytkownik serwisowy (zamiast root):

```bash
# Utworzenie użytkownika aplikacji
docker compose exec minio mc admin user add local testgen-app <silne_hasło>

# Polityka z pełnym dostępem do zasobników testgen-*
cat <<'EOF' > /tmp/testgen-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": [
        "arn:aws:s3:::testgen-*",
        "arn:aws:s3:::testgen-*/*"
      ]
    }
  ]
}
EOF

docker compose exec minio mc admin policy create local testgen-policy /tmp/testgen-policy.json
docker compose exec minio mc admin policy attach local testgen-policy --user testgen-app
```

### 8.3. Reguły cyklu życia

```bash
# Automatyczne usuwanie plików z testgen-exports po 30 dniach
docker compose exec minio mc ilm rule add local/testgen-exports \
  --expire-days 30

# Automatyczne usuwanie plików z testgen-uploads po 7 dniach
# (backup — główne czyszczenie realizuje Celery task cleanup)
docker compose exec minio mc ilm rule add local/testgen-uploads \
  --expire-days 7

# Weryfikacja reguł
docker compose exec minio mc ilm rule list local/testgen-uploads
docker compose exec minio mc ilm rule list local/testgen-exports
```

### 8.4. Weryfikacja

```bash
# Informacje o serwerze
docker compose exec minio mc admin info local

# Lista zasobników
docker compose exec minio mc ls local/
# Oczekiwane:
# [2026-09-16 10:00:00 UTC]     0B testgen-uploads/
# [2026-09-16 10:00:00 UTC]     0B testgen-results/
# [2026-09-16 10:00:00 UTC]     0B testgen-exports/
# [2026-09-16 10:00:00 UTC]     0B testgen-avatars/

# Konsola webowa MinIO
# http://localhost:9001 (login: MINIO_ROOT_USER / MINIO_ROOT_PASSWORD)

# Test uploadu
echo "test" | docker compose exec -T minio mc pipe local/testgen-uploads/test.txt
docker compose exec minio mc cat local/testgen-uploads/test.txt
docker compose exec minio mc rm local/testgen-uploads/test.txt
```

---

## Powiązane dokumenty

| Dokument | Opis |
|----------|------|
| [`getting-started.md`](./getting-started.md) | szybki start dla programistów |
| [`environment-setup.md`](./environment-setup.md) | pełna lista zmiennych środowiskowych |
| [`02-operacje.md`](./02-operacje.md) | operacje, kopie zapasowe, skalowanie (Story 9.7) |
| [`examples/`](./examples/) | przykładowe pliki konfiguracyjne |
