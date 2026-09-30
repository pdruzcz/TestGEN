# **9.3.** Dokumentacja wdrożeniowa

### **9.3.1.** Dokumentacja instalacji on-premises

**REQ-DEPLOY-DOC-001:** Dokumentacja wdrożeniowa musi zawierać
szczegółowe instrukcje instalacji on-premises.

**Struktura dokumentacji wdrożeniowej (150-200 stron):**

#### Część I: Przygotowanie środowiska

- **Wymagania systemowe**

  - Wymagania sprzętowe (CPU, RAM, Disk)

  - Systemy operacyjne (Linux, Windows Server)

  - Wymagane oprogramowanie (Docker, Kubernetes, PostgreSQL, etc.)

  - Wymagania sieciowe (porty, firewall)

- **Architektura deployment**

  - Single-node vs. Multi-node

  - High Availability setup

  - Load balancing

  - Disaster recovery

#### Część II: Instalacja krok po kroku

- **Instalacja Docker i Kubernetes**

- **Konfiguracja baz danych**

  - PostgreSQL setup

  - MongoDB setup

  - Redis setup

  - Inicjalizacja schematów

- **Deployment aplikacji**

  - Pobieranie obrazów Docker

  - Konfiguracja zmiennych środowiskowych

  - Deployment mikroserwisów

  - Konfiguracja API Gateway

- **Konfiguracja SSL/TLS**

  - Generowanie certyfikatów

  - Konfiguracja HTTPS

  - Reverse proxy setup

#### Część III: Konfiguracja i dostrajanie

- **Konfiguracja aplikacji**

- **Integracja z systemami autentykacji (LDAP, Active Directory,
  OAuth)**

- **Konfiguracja backupu**

- **Monitoring i logging**

- **Performance tuning**

#### Część IV: Utrzymanie i administracja

- **Procedury aktualizacji**

- **Backup i restore**

- **Skalowanie systemu**

- **Troubleshooting**

### **9.3.2.** Przykładowa instrukcja instalacji

#### Instalacja TestGEN on-premises - Quick Start

**Wymagania minimalne:**

- OS: Ubuntu 22.04 LTS / CentOS 8 / Windows Server 2019+

- CPU: 8 cores

- RAM: 32 GB

- Disk: 500 GB SSD

- Docker 24.x+

- Kubernetes 1.27+ (opcjonalnie)

**Krok 1: Przygotowanie środowiska**

\# Aktualizacja systemu sudo apt update && sudo apt upgrade -y \#
Instalacja Docker curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh \# Instalacja Docker Compose sudo apt install
docker-compose-plugin \# Weryfikacja instalacji docker \--version docker
compose version

**Krok 2: Pobranie konfiguracji TestGEN**

\# Pobranie repozytorium instalacyjnego git clone
https://github.com/testgen/on-premises.git cd on-premises \# Skopiowanie
przykładowej konfiguracji cp .env.example .env \# Edycja konfiguracji
nano .env

**Krok 3: Konfiguracja zmiennych środowiskowych**

\# .env file POSTGRES_HOST=localhost POSTGRES_PORT=5432
POSTGRES_DB=testgen POSTGRES_USER=testgen
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD MONGODB_HOST=localhost
MONGODB_PORT=27017 MONGODB_DB=testgen MONGODB_USER=testgen
MONGODB_PASSWORD=CHANGE_ME_STRONG_PASSWORD REDIS_HOST=localhost
REDIS_PORT=6379 REDIS_PASSWORD=CHANGE_ME_STRONG_PASSWORD
JWT_SECRET=CHANGE_ME_RANDOM_STRING_64_CHARS
API_BASE_URL=https://your-domain.com \# Licencja
LICENSE_KEY=YOUR_LICENSE_KEY_HERE

**Krok 4: Uruchomienie baz danych**

\# Uruchomienie PostgreSQL, MongoDB i Redis docker compose up -d
postgres mongodb redis \# Weryfikacja docker compose ps \# Inicjalizacja
schematów bazy danych docker compose run \--rm init-db

**Krok 5: Deployment aplikacji**

\# Uruchomienie wszystkich serwisów docker compose up -d \# Weryfikacja
statusu docker compose ps \# Sprawdzenie logów docker compose logs -f
api-gateway

**Krok 6: Weryfikacja instalacji**

\# Test health check curl http://localhost:8080/health \# Oczekiwany
output: { \"status\": \"healthy\", \"services\": { \"api_gateway\":
\"ok\", \"postgres\": \"ok\", \"mongodb\": \"ok\", \"redis\": \"ok\" } }

**Krok 7: Konfiguracja HTTPS (produkcja)**

\# Instalacja Certbot dla Let\'s Encrypt sudo apt install certbot \#
Generowanie certyfikatu sudo certbot certonly \--standalone -d
your-domain.com \# Konfiguracja Nginx jako reverse proxy sudo nano
/etc/nginx/sites-available/testgen \# Restart Nginx sudo systemctl
restart nginx

**Krok 8: Utworzenie pierwszego użytkownika administratora**

\# Utworzenie admina docker compose exec api python manage.py
create-admin \\ \--email admin@your-company.com \\ \--password CHANGE_ME
\# Login w przeglądarce https://your-domain.com

**Instalacja zakończona!** System TestGEN jest gotowy do użycia. Zaloguj
się używając powyższych danych i rozpocznij konfigurację pierwszego
projektu.

### **9.3.3.** Kubernetes Deployment

Dla większych wdrożeń zalecamy użycie Kubernetes:

\# Przykładowy Kubernetes deployment apiVersion: apps/v1 kind:
Deployment metadata: name: testgen-api namespace: testgen spec:
replicas: 3 selector: matchLabels: app: testgen-api template: metadata:
labels: app: testgen-api spec: containers: - name: api image:
testgen/api:latest ports: - containerPort: 8000 env: - name:
POSTGRES_HOST valueFrom: secretKeyRef: name: testgen-secrets key:
postgres-host - name: JWT_SECRET valueFrom: secretKeyRef: name:
testgen-secrets key: jwt-secret resources: requests: memory: \"2Gi\"
cpu: \"1000m\" limits: memory: \"4Gi\" cpu: \"2000m\" livenessProbe:
httpGet: path: /health port: 8000 initialDelaySeconds: 30 periodSeconds:
10 readinessProbe: httpGet: path: /ready port: 8000 initialDelaySeconds:
10 periodSeconds: 5 \-\-- apiVersion: v1 kind: Service metadata: name:
testgen-api-service namespace: testgen spec: selector: app: testgen-api
ports: - protocol: TCP port: 80 targetPort: 8000 type: LoadBalancer
