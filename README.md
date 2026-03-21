# Sentiment Analyst

Local-first advisor sentiment workflow with a Flutter client, a FastAPI backend, local AI services, and Docker-managed infrastructure.

## Local Architecture

- Flutter app in `frontend/assistant`
- FastAPI backend in `backend`
- Docker-managed infrastructure in `infra`
  - PostgreSQL
  - OpenSearch
  - OpenSearch Dashboards
  - MinIO
- Ollama runs on the host machine at `http://localhost:11434`

The backend can be run in either of these modes:

1. Host mode: Python virtualenv + Uvicorn
2. Docker mode: `backend/Dockerfile` image + `docker run`

## Prerequisites

- Docker Desktop or Docker Engine with Compose
- Python 3.11+
- Flutter SDK compatible with `frontend/assistant/pubspec.yaml`
- Ollama installed and running locally
- A pulled Ollama model matching `OLLAMA_MODEL` in `backend/.env`

## First-Time Setup

1. Copy the backend environment file:

```bash
cp backend/.env.example backend/.env
```

2. Optional: review infra defaults in `infra/.env.example`

3. Start infrastructure:

```bash
make infra-up
```

4. Ensure Ollama is running locally and serving your model:

```bash
curl http://localhost:11434/api/tags
```

## Option A: Run Backend On Host

1. Create the virtualenv:

```bash
make backend-venv
```

2. Install dependencies:

```bash
make backend-install
```

3. Apply migrations:

```bash
make backend-migrate
```

4. Start the API:

```bash
make backend-run
```

The API will be available at `http://localhost:8000`.

## Option B: Run Backend In Docker

This mode still expects Ollama to run on the host machine.

1. Copy `backend/.env.example` to `backend/.env` if you have not already done so.

2. Build the image:

```bash
make backend-docker-build
```

3. Apply migrations from the image:

```bash
make backend-docker-migrate
```

4. Start the API container:

```bash
make backend-docker-run
```

In Docker mode, the Makefile reads `backend/.env` and rewrites localhost-based endpoints to `host.docker.internal` so the container can reach host-published services:

- `DATABASE_URL` host is rewritten from `localhost` to `host.docker.internal`
- `OLLAMA_BASE_URL` host is rewritten from `localhost` to `host.docker.internal`
- `MINIO_ENDPOINT` host is rewritten from `localhost` to `host.docker.internal`

The `--add-host=host.docker.internal:host-gateway` flag is included for Linux compatibility. On macOS with Docker Desktop, `host.docker.internal` is available by default.

## Run The Flutter App

Install dependencies:

```bash
make frontend-install
```

Run the app:

```bash
make frontend-run
```

Analyze and test:

```bash
make frontend-analyze
make frontend-test
```

## Frontend Base URL Behavior

The Flutter app defaults to `http://localhost:8000` in `frontend/assistant/lib/core/config.dart`.

Use these values depending on where the app runs:

- iOS simulator on the same Mac: `http://localhost:8000`
- Android emulator: `http://10.0.2.2:8000`
- Physical device on local Wi-Fi: `http://<your-mac-ip>:8000`

If you need a different base URL, the app stores it under `api_base_url` in SharedPreferences via the existing config helpers.

## Verification

After startup, check the main services:

```bash
make verify
```

You can also verify them directly:

- FastAPI docs: `http://localhost:8000/docs`
- OpenSearch: `http://localhost:9200/_cluster/health`
- OpenSearch Dashboards: `http://localhost:5601`
- MinIO API health: `http://localhost:9000/minio/health/live`
- MinIO console: `http://localhost:9001`
- Ollama tags: `http://localhost:11434/api/tags`

## Troubleshooting

### PostgreSQL authentication fails

If `make backend-migrate` or `make backend-docker-migrate` fails with password authentication errors, your local Postgres volume may have been initialized with different credentials than the current env files.

Options:

- update `backend/.env` to match the credentials already stored in Postgres
- or recreate the local Postgres volume if you want to reset to the defaults in `infra/.env.example`

Resetting the volume is destructive to local database contents.

## Common Commands

```bash
make infra-up
make infra-down
make infra-logs
make backend-run
make backend-docker-build
make backend-docker-run
make frontend-run
make frontend-analyze
make frontend-test
make verify
```

## Supporting Docs

- `infra/README.md` for infra-specific detail
- `frontend/assistant/README.md` for app-specific notes
- `docos/architecture.md`, `docos/erd.md`, `docos/prd.md` for product and architecture context
