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
  - Jaeger
  - Prometheus
  - **Backend API** (FastAPI — optional, see Option C below)
- Ollama runs on the host machine at `http://localhost:11434`

## Flutter App Network Configuration

The Flutter app reads the backend base URL from the Settings screen and persists it via `SharedPreferences`.
The correct URL depends on how you are running the app:

| Scenario                              | Base URL                  |
| ------------------------------------- | ------------------------- |
| iOS Simulator (macOS host)            | `http://localhost:8000`   |
| Android Emulator                      | `http://10.0.2.2:8000`    |
| Physical device on same Wi-Fi network | `http://192.168.x.x:8000` |

The backend already binds to `0.0.0.0` (`make backend-run` uses `--host 0.0.0.0`), so no host change is needed.
CORS is configured to allow all origins in the current local build.

### Finding your machine's local IPv4 address (physical device)

```bash
# macOS
ipconfig getifaddr en0

# Or: System Settings → Wi-Fi → Details → IP Address
```

### Common failure points

- **Wrong IP or URL typo** — double-check with `curl http://<ip>:8000/health` from any machine on the network.
- **Backend bound to 127.0.0.1** — the default `make backend-run` uses `0.0.0.0`; if you started uvicorn manually, ensure `--host 0.0.0.0`.
- **Firewall blocking port 8000** — on macOS, System Settings → Network → Firewall → Options, or temporarily disable during local testing.
- **Device and machine on different networks** — both must be on the same Wi-Fi subnet; a guest network or personal hotspot will not work.
- **iOS physical device requires HTTPS** — for App Transport Security (ATS) exemptions in development, add `localhost` / the IP to `NSExceptionDomains` in `ios/Runner/Info.plist`, or use `http://` with ATS disabled (set `NSAllowsArbitraryLoads: true` for local dev only).

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

## Option B: Run Backend In Docker (standalone)

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

## Option C: Full Docker Compose Stack (infrastructure + backend)

This option brings up **all** services — infrastructure and the FastAPI backend — from a single Compose command. No separate `backend/.env` is needed; all backend environment variables are resolved from `infra/.env.example`.

**Prerequisites:** Ollama must still run on the host machine at `http://localhost:11434`.

1. Ensure Ollama is running:

```bash
curl http://localhost:11434/api/tags
```

2. Bring up the full stack (builds the backend image, activates the `backend` Compose profile which waits for healthy dependencies, then runs migrations and starts the API):

```bash
make stack-up
```

3. Verify all services are reachable:

```bash
make verify
```

The API will be available at `http://localhost:8000`.

### Startup Order

The backend service depends on health checks from postgres, opensearch, and minio before it starts. On first start, `alembic upgrade head` runs automatically inside the backend container before uvicorn is launched.

### Stopping The Full Stack

```bash
make stack-down
```

### Logs

```bash
make stack-logs
```

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
# Infrastructure only
make infra-up
make infra-down
make infra-logs

# Full stack (infrastructure + backend)
make stack-up
make stack-down
make stack-logs
make stack-migrate

# Backend on host
make backend-run
make backend-docker-build
make backend-docker-run

# Frontend
make frontend-run
make frontend-analyze
make frontend-test

# Verify endpoints
make verify
```

## Supporting Docs

- `infra/README.md` for infra-specific detail
- `frontend/assistant/README.md` for app-specific notes
- `docos/architecture.md`, `docos/erd.md`, `docos/prd.md` for product and architecture context
