# Dokumentacja wdrożeniowa — indeks

> Uruchamianie i utrzymanie środowisk TestGEN.

## Dokumenty

| Dokument | Zakres |
|---|---|
| [getting-started.md](getting-started.md) | Pierwsze uruchomienie lokalne (dev): monorepo, zależności, docker compose |
| [environment-setup.md](environment-setup.md) | Konfiguracja środowiska: zmienne env, sekrety, serwisy |
| [01-instalacja.md](01-instalacja.md) | **Instalacja produkcyjna:** wymagania systemowe, Docker Compose (single-node), Kubernetes/Helm (multi-node), SSL/TLS, konfiguracja PostgreSQL, Redis, RabbitMQ, MinIO |
| [02-operacje.md](02-operacje.md) | **Operacje produkcyjne:** backup/restore (PostgreSQL, Redis, MinIO), skalowanie horyzontalne, aktualizacje (rolling/blue-green/canary), monitoring (Prometheus + Grafana + Loki), disaster recovery |
| [examples/](examples/) | Pliki konfiguracyjne i skrypty: `.env.production`, `postgresql.conf`, `redis.conf`, `rabbitmq.conf`, `pgbouncer.ini`, `values.yaml`, `backup-*.sh`, `restore-postgres.sh`, `prometheus-rules.yml`, `grafana-dashboard.json` |

## Powiązane

Runbook operacyjny webhooków płatności: [../troubleshooting/tpay-sandbox-runbook.md](../troubleshooting/tpay-sandbox-runbook.md)
oraz [../architecture/billing/04-webhooki.md](../architecture/billing/04-webhooki.md).
