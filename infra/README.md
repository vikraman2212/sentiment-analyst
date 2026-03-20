# Local Infrastructure

This folder contains local infrastructure for the MVP.

## What runs here

- PostgreSQL (Docker)
- OpenSearch (Docker, custom build from `infra/opensearch/Dockerfile`)
- OpenSearch Dashboards (Docker)

## What does not run here

- Ollama is intentionally not defined in this Compose file because it is already running locally on your machine.

## Start full infra stack

```bash
docker compose -f infra/docker-compose.yml up -d
```

## Start only OpenSearch services

```bash
docker compose -f infra/docker-compose.yml up -d opensearch opensearch-dashboards
```

## Stop database

```bash
docker compose -f infra/docker-compose.yml down
```

## Connection details

- Host: `localhost`
- Port: `5432`
- Database: `advisor_db`
- User: `admin`
- Password: `localpassword`

## OpenSearch endpoints

- OpenSearch API: `http://localhost:9200`
- OpenSearch Dashboards: `http://localhost:5601`

## Notes

- OpenSearch security plugin is disabled for local development parity with your reference setup.
- If port `5432` is already in use, start PostgreSQL with an alternate host port:
  - `POSTGRES_PORT=5433 docker compose -f infra/docker-compose.yml up -d postgres`

## App environment hints

- Backend running on host machine:
  - `DATABASE_URL=postgresql+psycopg://admin:localpassword@localhost:5432/advisor_db`
  - `OLLAMA_BASE_URL=http://localhost:11434`
- Backend running in Docker:
  - `OLLAMA_BASE_URL=http://host.docker.internal:11434`


# LaunchDaemon (system install)
sudo launchctl disable system/org.postgresql.postgres