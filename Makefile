.PHONY: dev test migrate lint format build down logs clean ci-lint ci-test ci-build \
       celery-worker celery-beat celery-flower celery-inspect

# Start all services in development mode
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Run backend tests
test:
	cd backend && python -m pytest tests/ -v --tb=short

# Run Alembic migrations
migrate:
	cd backend && alembic upgrade head

# Run linters (Python + Angular)
lint:
	cd backend && python -m ruff check app/ tests/
	cd frontend && npx ng lint

# Auto-format code
format:
	cd backend && python -m ruff format app/ tests/
	cd frontend && npx prettier --write "src/**/*.{ts,html,scss}"

# Build production images
build:
	docker compose -f docker-compose.yml build

# Stop all services
down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# Show logs
logs:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Clean volumes and build artifacts
clean:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans

# --- Celery shortcuts ---

# Run Celery worker (default queue)
celery-worker:
	cd backend && celery -A app.workers.celery_app worker -Q default --loglevel=info

# Run Celery beat scheduler
celery-beat:
	cd backend && celery -A app.workers.celery_app beat --loglevel=info

# Run Flower monitoring UI
celery-flower:
	cd backend && celery --broker=${CELERY_BROKER_URL:-amqp://testgen:testgen_dev_password@localhost:5672//} flower --port=5555

# Inspect active Celery tasks
celery-inspect:
	cd backend && celery -A app.workers.celery_app inspect active

# --- CI targets (mirror Bitbucket Pipelines steps) ---

# CI: Run linting for backend + frontend
ci-lint:
	cd backend && ruff check app/ tests/
	cd backend && ruff format --check app/ tests/
	cd frontend && npx ng lint
	cd frontend && npx prettier --check "src/**/*.{ts,html,scss}"

# CI: Run tests with coverage + JUnit XML output
ci-test:
	cd backend && pytest tests/ -v --tb=short \
		--junitxml=test-results/backend-results.xml \
		--cov=app \
		--cov-report=xml:coverage/backend-coverage.xml \
		--cov-report=html:coverage/backend-html/ \
		--cov-fail-under=80
	cd frontend && npx ng test -- --coverage --ci

# CI: Build Docker images
ci-build:
	docker build -t testgen-backend:local backend/
	docker build -t testgen-frontend:local frontend/
