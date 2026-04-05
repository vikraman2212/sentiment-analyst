SHELL := /bin/bash

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend/assistant
INFRA_DIR := $(ROOT_DIR)/infra
BACKEND_IMAGE := sentiment-backend:local

.PHONY: infra-up infra-down infra-logs dev-up stack-up stack-down stack-logs stack-migrate agents-up agents-down agents-logs seed-db backend-install backend-migrate backend-run backend-test backend-lint backend-typecheck backend-docker-build backend-docker-migrate backend-docker-run backend-docker-stop frontend-install frontend-run frontend-run-web frontend-analyze frontend-test verify

infra-up:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example up -d
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example up -d --force-recreate minio-init

# Start infrastructure then the host backend in one command.
# Ctrl-C stops the backend; run make infra-down separately to tear down Docker services.
dev-up: infra-up backend-run

infra-down:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example down

infra-logs:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example logs -f

# Full stack — infrastructure + backend API (including Alembic migrations on startup)
stack-up:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend up -d --build

stack-down:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend down

stack-logs:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend logs -f

# Standalone agent containers — infra + backend API + email-agent worker as separate services
agents-up:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend --profile agents up -d --build

agents-down:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend --profile agents down

agents-logs:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend --profile agents logs -f

# Run only the Alembic migration step inside the compose network (one-shot container)
stack-migrate:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example --profile backend run --rm backend alembic upgrade head

# Load seed data into the running Postgres container.
# Run this after migrations have been applied (make stack-migrate or make backend-migrate).
# Sources infra/.env.example so the correct DB user / name are used automatically.
seed-db:
	@echo "Loading seed data into sentiment-postgres..."
	@set -a && . $(INFRA_DIR)/.env.example && set +a && \
		docker exec -i sentiment-postgres \
			psql -U "$${POSTGRES_USER:-admin}" -d "$${POSTGRES_DB:-advisor_db}" \
			< $(INFRA_DIR)/postgres/seed.sql
	@echo "Seed data loaded."

backend-install:
	cd $(BACKEND_DIR) && uv sync

backend-migrate:
	cd $(BACKEND_DIR) && uv run alembic upgrade head

backend-run:
	@pkill -f "uvicorn app.main" 2>/dev/null || true
	cd $(BACKEND_DIR) && uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

backend-test:
	cd $(BACKEND_DIR) && uv run pytest tests/ -q

backend-lint:
	cd $(BACKEND_DIR) && uv run ruff check .

backend-typecheck:
	cd $(BACKEND_DIR) && uv run mypy .

backend-docker-build:
	docker build -t $(BACKEND_IMAGE) $(BACKEND_DIR)

backend-docker-migrate:
	@set -a && source $(BACKEND_DIR)/.env && set +a && \
	docker run --rm \
		--add-host=host.docker.internal:host-gateway \
		--env-file $(BACKEND_DIR)/.env \
		-e DATABASE_URL="$${DATABASE_URL/localhost/host.docker.internal}" \
		-e OLLAMA_BASE_URL="$${OLLAMA_BASE_URL/localhost/host.docker.internal}" \
		-e MINIO_ENDPOINT="$${MINIO_ENDPOINT/localhost/host.docker.internal}" \
		$(BACKEND_IMAGE) \
		alembic upgrade head

backend-docker-run:
	@set -a && source $(BACKEND_DIR)/.env && set +a && \
	docker run --rm -p 8000:8000 \
		--add-host=host.docker.internal:host-gateway \
		--env-file $(BACKEND_DIR)/.env \
		-e DATABASE_URL="$${DATABASE_URL/localhost/host.docker.internal}" \
		-e OLLAMA_BASE_URL="$${OLLAMA_BASE_URL/localhost/host.docker.internal}" \
		-e MINIO_ENDPOINT="$${MINIO_ENDPOINT/localhost/host.docker.internal}" \
		$(BACKEND_IMAGE)

backend-docker-stop:
	@container_ids=$$(docker ps -q --filter ancestor=$(BACKEND_IMAGE)); \
	if [ -n "$$container_ids" ]; then docker stop $$container_ids; fi

frontend-install:
	cd $(FRONTEND_DIR) && flutter pub get

frontend-run:
	cd $(FRONTEND_DIR) && flutter run -d macos

frontend-run-web:
	cd $(FRONTEND_DIR) && flutter run -d chrome

frontend-analyze:
	cd $(FRONTEND_DIR) && flutter analyze

frontend-test:
	cd $(FRONTEND_DIR) && flutter test

verify:
	@echo "Checking local endpoints..."
	@curl -fsS http://localhost:8000/docs >/dev/null && echo "backend: ok" || echo "backend: unavailable"
	@curl -fsS http://localhost:9200/_cluster/health >/dev/null && echo "opensearch: ok" || echo "opensearch: unavailable"
	@curl -fsS http://localhost:9000/minio/health/live >/dev/null && echo "minio: ok" || echo "minio: unavailable"
	@curl -fsS http://localhost:11434/api/tags >/dev/null && echo "ollama: ok" || echo "ollama: unavailable"