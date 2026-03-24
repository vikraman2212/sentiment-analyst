Architecture: AI Financial Advisor — Advisor Sentiment Platform
1. Executive Summary
Product Vision: A completely "Local-First" AI assistant for financial advisors that captures unstructured voice notes, securely extracts structured context, and automatically drafts highly personalized client emails.
Target User: Solo Financial Advisor.
Architecture Principles: 100% local network operation (Zero-Cloud Infrastructure for DB, API, and AI inference) ensuring zero cost and maximum data privacy. Local open-source models (Ollama/Whisper) with easy swap to cloud models (OpenAI/Anthropic) in future. Uses native mailto: links for email delivery.
2. System Architecture
The system operates on a "Thin Client, Thick Local Engine" model. The Flutter app acts as the UI only. Audio is uploaded directly from the client to MinIO object storage via a pre-signed URL — audio bytes never pass through the FastAPI process. MinIO fires a webhook event notification to the backend, which then downloads the file, transcribes, and extracts context.

Crucial Architecture Note: To prevent entity resolution errors (e.g., multiple clients named "John"), the Flutter App is the source of truth for entity ID. The object key in MinIO is always scoped as `{client_id}/{uuid}.ext`, so the backend extracts the client identity from the key path — no separate parameter needed on the webhook.

sequenceDiagram
    autonumber
    actor Advisor
    participant Flutter App
    participant FastAPI (Host :8000)
    participant MinIO (Docker :9000)
    participant Postgres (Docker :5434)
    participant OpenSearch (Docker :9200)
    participant Ollama (Host :11434)
    participant Whisper (Host, in-process)

    rect rgb(230, 240, 255)
    Note over Advisor, Whisper (Host, in-process): Phase 1: Data Capture & Extraction
    Advisor->>Flutter App: Selects Client (searchable dropdown)
    Advisor->>Flutter App: Records Voice Memo
    Flutter App->>FastAPI (Host :8000): POST /api/v1/audio/presign {client_id, filename, content_type}
    FastAPI (Host :8000)-->>Flutter App: {upload_url, object_key}
    Flutter App->>MinIO (Docker :9000): PUT audio bytes directly via presigned URL
    MinIO (Docker :9000)->>FastAPI (Host :8000): POST /api/v1/audio/webhook (S3 event notification)
    Note right of FastAPI (Host :8000): Background task — returns 200 immediately
    FastAPI (Host :8000)->>Whisper (Host, in-process): Transcribe audio (faster-whisper, asyncio.to_thread)
    FastAPI (Host :8000)->>Postgres (Docker :5434): INSERT interaction {transcript, audio_file_key}
    FastAPI (Host :8000)->>Ollama (Host :11434): Extract context tags (JSON format enforced)
    Ollama (Host :11434)-->>FastAPI (Host :8000): Structured context JSON
    FastAPI (Host :8000)->>Postgres (Docker :5434): INSERT client_context rows
    FastAPI (Host :8000)->>OpenSearch (Docker :9200): POST /llm-audits/_doc (async audit log)
    end

    rect rgb(230, 255, 230)
    Note over FastAPI (Host :8000), Ollama (Host :11434): Phase 2: Trigger & Generate (Scheduled or On-Demand)
    Note right of FastAPI (Host :8000): APScheduler fires daily at 08:00 AEST, or POST /api/v1/generate
    FastAPI (Host :8000)->>Postgres (Docker :5434): Fetch financial_profile + client_context for client
    Postgres (Docker :5434)-->>FastAPI (Host :8000): Returns financials + context tags
    FastAPI (Host :8000)->>Ollama (Host :11434): System prompt with assembled context
    Ollama (Host :11434)-->>FastAPI (Host :8000): Email draft text
    FastAPI (Host :8000)->>Postgres (Docker :5434): INSERT message_draft {status: pending}
    FastAPI (Host :8000)->>OpenSearch (Docker :9200): POST /llm-audits/_doc
    end

    rect rgb(255, 240, 230)
    Note over Advisor, Postgres (Docker :5434): Phase 3: Human-in-the-Loop Review
    Advisor->>Flutter App: Opens "Pending Drafts" tab
    Flutter App->>FastAPI (Host :8000): GET /api/v1/drafts/pending
    FastAPI (Host :8000)-->>Flutter App: Draft list with context tags used
    Advisor->>Flutter App: Approves Draft → Opens native Mail app (mailto:)
    Flutter App->>FastAPI (Host :8000): PATCH /api/v1/message-drafts/{id}/status {status: sent}
    end


3. Entity Relationship Diagram (ERD)
This defines the local PostgreSQL database schema. It strictly separates financial "hard numbers" from the AI-extracted "soft context" to prevent hallucination.
erDiagram
    ADVISORS ||--o{ CLIENTS : manages
    CLIENTS ||--|| FINANCIAL_PROFILES : has
    CLIENTS ||--o{ CLIENT_CONTEXT : generates
    CLIENTS ||--o{ INTERACTIONS : records
    CLIENTS ||--o{ MESSAGE_DRAFTS : receives
    CLIENTS ||--o{ GENERATION_FAILURES : logs

    ADVISORS {
        uuid id PK
        string full_name
        string email
        string default_tone
    }

    CLIENTS {
        uuid id PK
        uuid advisor_id FK
        string first_name
        string last_name
        date next_review_date
    }

    FINANCIAL_PROFILES {
        uuid id PK
        uuid client_id FK
        decimal total_aum
        decimal ytd_return_pct
        string risk_profile
    }

    CLIENT_CONTEXT {
        uuid id PK
        uuid client_id FK
        string category "personal_interest | financial_goal | family_event | risk_tolerance"
        string content "e.g. Loves cricket"
        uuid source_interaction_id FK
    }

    INTERACTIONS {
        uuid id PK
        uuid client_id FK
        string type "voice_memo"
        text raw_transcript
        string audio_file_key "MinIO object key: {client_id}/{uuid}.ext"
        timestamp created_at
    }

    MESSAGE_DRAFTS {
        uuid id PK
        uuid client_id FK
        string trigger_type
        text generated_content
        string status "pending | sent"
    }

    GENERATION_FAILURES {
        uuid id PK
        uuid client_id FK
        string trigger_type
        string message_id
        text error_detail
        timestamp failed_at
        bool resolved
    }


4. Mobile UI Blueprint (Flutter)
The mobile app is strictly task-oriented with a Bottom Navigation Bar containing two tabs.
Tab 1: Capture (Data In)
Element 1 (Critical): Searchable Client Dropdown. Recording is disabled until a client is selected.
Element 2: "Hold to Record" button with audio wave animation and timer.
Upload Flow: On stop, the app requests a presigned URL from `POST /api/v1/audio/presign`, then PUTs the audio file directly to MinIO. The backend is automatically notified via MinIO's webhook — no second API call from the app is required.
Tab 2: Inbox (Data Out & Review)
List View: Shows pending message_drafts (Client Name, Trigger Type).
Detail View: Shows the AI-generated draft and the context tags the AI used to write it.
Action: "Approve & Send" opens mailto: on the device and PATCHes the draft status to `sent` via `PATCH /api/v1/message-drafts/{id}/status`.
5. Local Infrastructure (Docker Compose)
All stateful services run in Docker. The FastAPI backend and Ollama run on the host (not in Docker) to avoid GPU/audio complexity. Postgres is mapped to host port 5434 to avoid conflicts.

Services:

| Container | Image | Host Port(s) | Purpose |
|---|---|---|---|
| sentiment-postgres | postgres:15-alpine | 5434 | Primary database |
| sentiment-opensearch | infra-opensearch (custom) | 9200, 9300 | LLM audit log storage |
| sentiment-opensearch-dashboards | opensearchproject/opensearch-dashboards | 5601 | OpenSearch UI |
| sentiment-minio | minio/minio:latest | 9000, 9001 | Audio object storage + S3 webhook events |
| sentiment-minio-init | minio/mc:latest | — | One-shot bucket + event subscription bootstrap |
| sentiment-jaeger | jaegertracing/all-in-one:1.56 | 16686, 4317, 4318 | Distributed trace collection (OTLP) + UI |
| sentiment-prometheus | prom/prometheus:v2.51.2 | 9090 | Metrics scraping from backend /metrics |
| sentiment-backend | backend Dockerfile | 8000 (profile: backend) | Optional containerised API (dev uses host) |

MinIO Webhook Integration:
- On startup, `minio-init` registers `audio-uploads` bucket with an `s3:ObjectCreated:*` webhook pointing to `http://host.docker.internal:8000/api/v1/audio/webhook`.
- MinIO sends `Authorization: Bearer <MINIO_WEBHOOK_SECRET>` with each notification.
- The backend strips the `Bearer ` prefix before comparing the token.
- Object keys use the pattern `{client_id}/{uuid}.ext` — the backend parses `client_id` from the path.

Ollama runs natively on the host (port 11434). It is not containerised.

6. Observability Stack
Three complementary pillars:

| Pillar | Mechanism | Where to View |
|---|---|---|
| Distributed Traces | OpenTelemetry SDK → OTLP HTTP → Jaeger | http://localhost:16686 |
| Metrics | `prometheus_client` counters/histograms exposed at `GET /metrics` (pull) | http://localhost:9090 |
| LLM Audit Logs | Async `structlog` → OpenSearch `llm-audits` index | http://localhost:5601 |

Prometheus scrapes `host.docker.internal:8000/metrics` every 15 s. Traced instrumentation covers FastAPI, SQLAlchemy, and httpx automatically via `opentelemetry-instrumentation-*`.

Custom metrics defined in `app/core/telemetry.py`:
- `sentiment_extraction_requests_total` — extraction pipeline executions by status
- `sentiment_extraction_duration_seconds` — end-to-end extraction latency histogram
- `sentiment_generation_requests_total` — generation jobs by trigger type and status
- `sentiment_llm_calls_total` — Ollama calls by pipeline and model
- `sentiment_llm_latency_seconds` — Ollama call latency histogram
- `sentiment_worker_queue_depth` — current in-memory generation queue depth
- `sentiment_scheduler_runs_total` — APScheduler daily trigger counts

7. Iteration Plan & Timeline (10 Weeks)
gantt
    title AI Financial Advisor Delivery Timeline (10 Weeks)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Sprint 1: Data In
    Docker: DB & MinIO Setup           :crit, s1_1, 2026-03-23, 3d
    FastAPI Presign + Webhook Flow     :s1_2, after s1_1, 4d
    Ollama Extraction Integration      :s1_3, after s1_2, 3d
    Flutter Audio Capture + Presign UI :s1_4, after s1_1, 6d

    section Sprint 2: Data Out
    Context Injection Logic            :crit, s2_1, 2026-04-06, 4d
    OpenSearch + Jaeger + Prometheus   :s2_2, after s2_1, 3d
    Prompt Engineering (Local AI)      :s2_3, after s2_2, 5d
    APScheduler + Generation Worker    :s2_4, after s2_2, 3d

    section Sprint 3: UI & Review
    Local Network Config (Wi-Fi)   :crit, s3_1, 2026-04-20, 3d
    Flutter Dashboard & Review     :s3_2, after s3_1, 6d
    Mailto: Delivery Integration   :s3_3, after s3_2, 5d
    
    section Sprint 4: Polish
    Iterative Prompt Testing       :s4_1, 2026-05-04, 7d
    App Error Handling             :s4_2, 2026-05-04, 7d
    CSV to Postgres Data Import    :s4_3, after s4_2, 5d
    
    section Sprint 5: Local Prod
    Dockerize FastAPI App          :crit, s5_1, 2026-05-18, 4d
    Build Flutter Local APK/IPA    :s5_2, after s5_1, 4d
    System Stress Test             :s5_3, after s5_2, 4d


