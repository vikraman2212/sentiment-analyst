Engineering Requirements Document
Project: AI Financial Advisor — Advisor Sentiment Platform
Author: Solo Developer
Date: March 2026
1. Technology Stack Specifications
1.1. Mobile Client (Frontend)
Framework: Flutter (Dart 3.x)
State Management: Provider (minimal global state).
Core Packages:
record: For microphone access and .webm/.m4a recording.
http / dio: For REST API communication.
url_launcher: For invoking native OS email clients (mailto:).
1.2. API Gateway & Middleware (Backend)
Framework: FastAPI (Python 3.11+)
Server: Uvicorn with --reload (dev), bound to 0.0.0.0:8000.
ORM: SQLAlchemy 2.0 (Async + mapped_column) + Alembic migrations.
Validation: Pydantic v2 (request/response schemas + LLM JSON enforcement).
Background Tasks: APScheduler (daily generation CRON) + FastAPI BackgroundTasks (webhook extraction).
Queue: In-memory async queue (GenerationWorker) — swappable to Redis/SQS.
Logging: structlog (structured JSON to stdout).
Telemetry: OpenTelemetry SDK → Jaeger (traces) + prometheus_client → Prometheus (metrics).
1.3. Object Storage
MinIO (S3-compatible, Docker). Audio is uploaded directly from the Flutter client to MinIO via pre-signed PUT URLs. FastAPI never receives audio bytes in the request body. MinIO fires S3-compatible webhook notifications to the backend on ObjectCreated events.
1.4. Local AI Engine
Transcription: faster-whisper (Python library, runs in asyncio.to_thread on host).
LLM Inference: ollama-python SDK (Ollama runs natively on host port 11434).
Extraction Model: llama3.2 (JSON format enforced via Ollama format="json").
Generation Model: llama3.2 / mistral (temperature-tuned for professional email).
2. API Contract (RESTful Endpoints)
Base path: /api/v1. All request and response bodies are application/json unless noted.
2.1. Health
GET /health
Response: 200 OK {"status": "ok"}
2.2. Advisors
GET    /advisors/              — List all advisors
POST   /advisors/              — Create advisor {full_name, email, default_tone}
GET    /advisors/{id}          — Get advisor by ID
PATCH  /advisors/{id}          — Update advisor fields
GET    /advisors/{id}/clients  — List clients for an advisor
2.3. Clients
GET    /clients/               — List clients (optional ?advisor_id= filter)
POST   /clients/               — Create client {first_name, last_name, advisor_id, next_review_date}
GET    /clients/{id}           — Get client by ID
GET    /clients/{id}/interactions    — List interactions for a client
GET    /clients/{id}/message-drafts  — List drafts for a client
2.4. Audio Ingestion (Two-Step MinIO Upload)
Step 1 — Request a presigned upload URL:
POST /audio/presign
Purpose: Returns a pre-signed PUT URL so the Flutter app can upload audio directly to MinIO.
Request:
{
  "client_id": "uuid",
  "filename": "recording.webm",
  "content_type": "audio/webm"
}
Response: 200 OK
{
  "upload_url": "http://localhost:9000/audio-uploads/...?X-Amz-Signature=...",
  "object_key": "{client_id}/{uuid}.webm",
  "expires_in": 300
}

Step 2 — MinIO fires event notification (automatic):
POST /audio/webhook
Purpose: Receives S3-compatible ObjectCreated event from MinIO and queues background extraction.
Authentication: Authorization: Bearer <MINIO_WEBHOOK_SECRET> header.
Object key format: {client_id}/{uuid}.ext — client identity is parsed from the path.
Response: 200 OK {"status": "accepted", "queued": 1}
The webhook returns immediately; Whisper transcription and Ollama extraction run as a BackgroundTask.

Manual/Backfill trigger:
POST /audio/process
Purpose: Download an existing MinIO object and run the full extraction pipeline synchronously. Use to reprocess files if the webhook was missed.
Request:
{
  "client_id": "uuid",
  "object_key": "{client_id}/{uuid}.webm"
}
Response: 201 Created
{
  "status": "success",
  "extracted_tags_count": 3,
  "interaction_id": "uuid"
}

2.5. Interactions
POST /interactions/                       — Create interaction record manually
GET  /clients/{client_id}/interactions    — List interactions for a client
2.6. Draft Generation
POST /generate
Purpose: Generate a personalised draft email for a client on demand (also triggered by APScheduler daily).
Request:
{
  "client_id": "uuid",
  "trigger_type": "half_yearly_review",
  "force": false
}
Response: 201 Created
{
  "draft_id": "uuid",
  "client_id": "uuid",
  "trigger_type": "half_yearly_review",
  "generated_content": "Hi John, ..."
}

GET /generation/failures
Purpose: List failed generation jobs from the dead-letter table.
Response: 200 OK [{id, client_id, trigger_type, error_detail, failed_at, resolved}]
2.7. Draft Management
GET    /drafts/pending                        — List all pending drafts (Inbox tab)
POST   /message-drafts/                       — Create draft manually
GET    /clients/{client_id}/message-drafts    — List drafts for a client
PATCH  /message-drafts/{id}/status            — Update draft status {status: "sent" | "pending"}

GET /drafts/pending response shape:
[
  {
    "id": "uuid",
    "client_id": "uuid",
    "client_name": "John Doe",
    "trigger_type": "half_yearly_review",
    "generated_content": "Hi John, ...",
    "status": "pending"
  }
]

2.8. Scheduler
POST /scheduler/trigger
Purpose: Manually trigger the daily generation job (useful for dev/testing).
Response: 200 OK {"status": "triggered"}
3. AI Pipeline Specifications
3.1. Pipeline 1: Extraction (Audio → JSON)
Whisper Step: faster_whisper.WhisperModel("base.en").transcribe(audio_file_path) — runs in asyncio.to_thread.
INSERT Interaction row with transcript and audio_file_key.
Ollama Step:
  - Send transcript to Ollama with format="json".
  - System Prompt enforces JSON array output with keys: category (enum: personal_interest | financial_goal | family_event | risk_tolerance) and content (string).
INSERT client_context rows (one per extracted tag).
LLM Audit: async POST to OpenSearch /llm-audits/_doc regardless of outcome.
Failure handling: extraction failure is non-fatal — the interaction row is saved even if Ollama errors. The tag count will be 0.
3.2. Pipeline 2: Generation (Context → Email Text)
Triggered by APScheduler at 08:00 AEST daily, or manually via POST /generate.
Context Assembly: JOIN financial_profiles + client_context for the target client.
Ollama Step (system prompt):
"You are an elite financial advisor. Write a 4-sentence email inviting the client to a review.
CLIENT PROFILE:
Name: {first_name}
AUM: ${aum}
YTD Return: {ytd_pct}%
RECENT CONTEXT:
{context_list}
INSTRUCTIONS: Weave one piece of recent context into the financial update. Do not use exact dollar amounts. Be warm and professional. Output ONLY the email body."
On failure: INSERT generation_failures row for observability. Worker retries are not automatic — operator can view failures via GET /generation/failures and re-trigger manually.
4. Telemetry & Auditing Implementation
All AI operations are logged to the local OpenSearch cluster asynchronously.
Implementation: LlmAuditService in app/services/llm_audit.py.
Trigger: Called after every Ollama invocation (both extraction and generation pipelines).
Index: llm-audits
Document schema:
{
  "timestamp": "2026-03-25T14:00:00Z",
  "pipeline": "extraction | generation",
  "client_id": "uuid",
  "model": "llama3.2",
  "prompt_tokens": 450,
  "completion_tokens": 45,
  "latency_ms": 1250,
  "status": "success | error",
  "raw_prompt": "...",
  "raw_response": "..."
}

Prometheus metrics exposed at GET /metrics (scraped by Prometheus container):
- sentiment_extraction_requests_total{status}
- sentiment_extraction_duration_seconds (histogram)
- sentiment_generation_requests_total{trigger_type, status}
- sentiment_llm_calls_total{pipeline, model}
- sentiment_llm_latency_seconds (histogram)
- sentiment_worker_queue_depth (gauge)
- sentiment_scheduler_runs_total{status}

OpenTelemetry traces sent to Jaeger at http://localhost:4318/v1/traces (OTLP HTTP). OTLP metrics push is intentionally disabled — Prometheus pull is the sole metrics path.
5. Security & Networking Constraints
CORS: CORSMiddleware configured in app/core/middleware.py. Allows * in dev (restrict to specific IP in production).
Network Binding: Uvicorn bound to 0.0.0.0:8000 so the Flutter app on the same Wi-Fi can reach the backend.
MinIO Webhook Auth: MINIO_WEBHOOK_SECRET shared secret. MinIO sends Authorization: Bearer <secret>; backend strips the Bearer prefix before comparing. Secret is set via MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_primary env var on the MinIO container.
No PII in logs: structlog configuration must never log email addresses, full names, or financial amounts at debug level or above in production paths.
6. Database Migrations (Alembic)
Migration files in alembic/versions/. Naming convention: {seq}_{snake_case_description}.py.
All foreign keys are configured with ON DELETE CASCADE.
Each migration must have a correct downgrade() that exactly reverses upgrade().
Current migrations:
- 0001_initial_schema.py — 6 core tables
- 0002_add_interaction_audio_file_key.py — audio_file_key column on interaction
- 0003_add_pending_draft_unique_index.py — unique index on (client_id, status=pending)
- 0004_add_generation_failures.py — generation_failures dead-letter table
