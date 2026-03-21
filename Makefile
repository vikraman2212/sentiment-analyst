SHELL := /bin/bash

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend/assistant
INFRA_DIR := $(ROOT_DIR)/infra
BACKEND_IMAGE := sentiment-backend:local

.PHONY: infra-up infra-down infra-logs backend-venv backend-install backend-migrate backend-run backend-docker-build backend-docker-migrate backend-docker-run backend-docker-stop frontend-install frontend-run frontend-analyze frontend-test verify

infra-up:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example up -d

infra-down:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example down

infra-logs:
	docker compose -f $(INFRA_DIR)/docker-compose.yml --env-file $(INFRA_DIR)/.env.example logs -f

backend-venv:
	cd $(BACKEND_DIR) && python3 -m venv .venv

backend-install:
	cd $(BACKEND_DIR) && [ -d .venv ] || python3 -m venv .venv
	cd $(BACKEND_DIR) && source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

backend-migrate:
	cd $(BACKEND_DIR) && [ -d .venv ] || python3 -m venv .venv
	cd $(BACKEND_DIR) && source .venv/bin/activate && alembic upgrade head

backend-run:
	cd $(BACKEND_DIR) && [ -d .venv ] || python3 -m venv .venv
	cd $(BACKEND_DIR) && source .venv/bin/activate && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

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
	cd $(FRONTEND_DIR) && flutter run

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