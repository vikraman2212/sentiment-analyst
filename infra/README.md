# Local Infrastructure

This folder contains the Docker-managed local infrastructure for the MVP.

For the full startup flow, use the root [README.md](../README.md). This file focuses only on infra-specific details.

## Services In Compose

- PostgreSQL
- OpenSearch
- OpenSearch Dashboards (LLM audit visualisation)
- MinIO
- Jaeger (OTLP trace ingestion + UI)
- Prometheus (metrics scraping)
- **Backend** (FastAPI API server — added in Sprint 5)

## Service Not In Compose

- Ollama is intentionally not defined here. It must run on the host machine at `http://localhost:11434`. The backend service reaches it via `host.docker.internal:11434`.

## Start Infrastructure Only (no backend)

From the repository root:

```bash
make infra-up
```

Direct Compose command:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.example up -d
```

## Start Full Stack (infrastructure + backend)

```bash
make stack-up
```

This activates the `backend` Compose profile, builds the backend image (if needed), waits for postgres/opensearch/minio health checks to pass, runs Alembic migrations, and then starts the API server on port 8000.

Direct Compose command:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.example --profile backend up -d --build
```

## Stop

```bash
# Infra only
make infra-down

# Full stack
make stack-down
```

## Stream Logs

```bash
# Infra only
make infra-logs

# Full stack
make stack-logs
```

## Connection Details

### PostgreSQL

- Host: `localhost`
- Port: `5432`
- Database: `advisor_db`
- User: `admin`
- Password: `localpassword`

### OpenSearch

- API: `http://localhost:9200`
- Dashboards: `http://localhost:5601`

### MinIO

- API: `http://localhost:9000`
- Console: `http://localhost:9001`
- Access key: `minioadmin`
- Secret key: `minioadmin`

### Jaeger (Traces)

- UI: `http://localhost:16686`
- OTLP gRPC: `localhost:4317`
- OTLP HTTP: `http://localhost:4318`
- Enable in the backend via `OTEL_ENABLED=true` in `infra/.env.example` (defaults to the `jaeger` service inside compose)

### Prometheus (Metrics)

- UI / query: `http://localhost:9090`
- Scrapes the backend `/metrics` endpoint every 15 s
- When the backend runs in compose the scrape target is `backend:8000` (the compose service name)
- If you run the backend on the host instead, set the target to `host.docker.internal:8000` in `infra/prometheus/prometheus.yml`

### OpenSearch Dashboards (Visualisation)

- UI: `http://localhost:5601`
- Use this to build index-pattern dashboards over the `llm-audit-*` index
- No Grafana needed — OpenSearch Dashboards ships bundled with the existing OpenSearch container

### Backend API (when running in compose)

- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/health/ready`

## Environment Variables

Copy `infra/.env.example` to `infra/.env` to override defaults. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `POSTGRES_USER` | `admin` | |
| `POSTGRES_PASSWORD` | `localpassword` | |
| `POSTGRES_DB` | `advisor_db` | |
| `POSTGRES_PORT` | `5432` | Change if local port 5432 is occupied |
| `MINIO_ACCESS_KEY` | `minioadmin` | Must match MinIO container credentials |
| `MINIO_SECRET_KEY` | `minioadmin` | Must match MinIO container credentials |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama runs on the host |
| `OLLAMA_EXTRACTION_MODEL` | `llama3.2` | |
| `OLLAMA_GENERATION_MODEL` | `llama3.2` | |
| `LOG_LEVEL` | `INFO` | |
| `WHISPER_MODEL` | `base.en` | |
| `SCHEDULER_SECRET` | `change-me-in-production` | Used to authenticate the scheduler trigger endpoint |
| `OTEL_ENABLED` | `false` | Set to `true` to export traces to Jaeger |
| `OTEL_ENDPOINT` | `http://jaeger:4318` | OTLP HTTP collector; defaults to the Jaeger compose service |

## Notes

- OpenSearch security is disabled for local development.
- If port `5432` is already in use, set `POSTGRES_PORT=5433` (or another free port) in `infra/.env.example` before running compose.
- The backend container reaches Ollama on the host via `host.docker.internal`. On Linux, the `extra_hosts` entry in the compose file maps this to the host gateway automatically. On macOS/Windows with Docker Desktop it resolves by default.

## Observability Verification

After `make stack-up`, verify each observability service is reachable:

```bash
# Jaeger UI
open http://localhost:16686

# Prometheus targets (backend should appear as UP)
open http://localhost:9090/targets

# Prometheus graph (verify sentiment_* series are present)
open http://localhost:9090/graph

# OpenSearch Dashboards (LLM audit index visualisation)
open http://localhost:5601
```

To test the OTLP trace pipeline, set `OTEL_ENABLED=true` in `infra/.env.example` and restart the stack:

```bash
make stack-down && make stack-up
```

Traces will appear in the Jaeger UI under the `sentiment-analyst-backend` service name.

To verify backend metrics, exercise an upload or generation flow and query examples such as:

- `sentiment_extraction_requests_total`
- `sentiment_generation_requests_total`
- `sentiment_scheduler_runs_total`
- `sentiment_worker_messages_processed_total`

## Backend Networking Notes

Inside Compose, service-to-service URLs use compose service names:

- `DATABASE_URL=postgresql+psycopg://admin:localpassword@postgres:5432/advisor_db`
- `MINIO_ENDPOINT=http://minio:9000`
- `OPENSEARCH_URL=http://opensearch:9200`
- `OTEL_ENDPOINT=http://jaeger:4318`

These are resolved automatically by the Docker compose network and are set in the backend service environment in `docker-compose.yml`.

