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

## Service Not In Compose

- Ollama is intentionally not defined here. It must run on the host machine at `http://localhost:11434`.

## Start Infra

From the repository root:

```bash
make infra-up
```

Direct Compose command:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.example up -d
```

## Stop Infra

```bash
make infra-down
```

Direct Compose command:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.example down
```

## Stream Logs

```bash
make infra-logs
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
- Enable in the backend via `OTEL_ENABLED=true` and `OTEL_ENDPOINT=http://localhost:4318`

### Prometheus (Metrics)

- UI / query: `http://localhost:9090`
- Scrapes the backend `/metrics` endpoint every 15 s
- Scrape target configured in `infra/prometheus/prometheus.yml`

### OpenSearch Dashboards (Visualisation)

- UI: `http://localhost:5601`
- Use this to build index-pattern dashboards over the `llm-audit-*` index
- No Grafana needed — OpenSearch Dashboards ships bundled with the existing OpenSearch container

## Notes

- OpenSearch security is disabled for local development.
- If port `5432` is already in use, override it when starting Compose:

```bash
POSTGRES_PORT=5433 docker compose -f infra/docker-compose.yml --env-file infra/.env.example up -d postgres
```

## Observability Verification

After `make infra-up`, verify each observability service is reachable:

```bash
# Jaeger UI
open http://localhost:16686

# Prometheus targets (backend should appear as UP)
open http://localhost:9090/targets

# OpenSearch Dashboards (LLM audit index visualisation)
open http://localhost:5601
```

To test the OTLP trace pipeline, set these env vars in the backend and send a request:

```bash
OTEL_ENABLED=true
OTEL_ENDPOINT=http://localhost:4318
```

Traces will appear in the Jaeger UI under the `sentiment-analyst-backend` service name.

## Backend Networking Hints

If the backend runs on the host machine:

- `DATABASE_URL=postgresql+psycopg://admin:localpassword@localhost:5432/advisor_db`
- `MINIO_ENDPOINT=http://localhost:9000`
- `OLLAMA_BASE_URL=http://localhost:11434`

If the backend runs in Docker:

- the hostnames in `DATABASE_URL`, `MINIO_ENDPOINT`, and `OLLAMA_BASE_URL` should use `host.docker.internal`
- the root Makefile derives these Docker-safe values from `backend/.env`
