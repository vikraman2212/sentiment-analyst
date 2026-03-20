Product Requirements Document (PRD): AI Financial Advisor MVP
1. Executive Summary
Product Vision: A completely "Local-First" AI assistant for financial advisors that captures unstructured voice notes, securely extracts structured context, and automatically drafts highly personalized client emails.
Target User: Solo Financial Advisor.
MVP Constraints: Built by a solo developer. Prioritizes 100% local network operation (Zero-Cloud Infrastructure for DB, API, and AI inference) to ensure absolute zero cost and maximum data privacy. Uses local open-source models (Ollama/Whisper) with the ability to easily swap to priced cloud models (OpenAI/Anthropic) in future iterations. Uses native mailto: links for delivery.
2. System Architecture
The system operates on a "Thin Client, Thick Local Engine" model. The Flutter app acts merely as an interface, while the database, telemetry, and AI processing happen entirely on the local Dockerized environment.
Crucial Architecture Note: To prevent entity resolution errors (e.g., multiple clients named "John"), the Flutter App acts as the source of truth for entity ID. The client_id is passed as a strict parameter alongside the audio file.
sequenceDiagram
    autonumber
    actor Advisor
    participant Flutter App (Local IP)
    participant FastAPI (Local/Docker)
    participant Postgres DB (Docker)
    participant OpenSearch (Docker)
    participant Local AI (Whisper/Ollama)

    rect rgb(230, 240, 255)
    Note over Advisor, Local AI (Whisper/Ollama): Phase 1: Data Capture & Extraction
    Advisor->>Flutter App (Local IP): Selects Client (UI Dropdown)
    Advisor->>Flutter App (Local IP): Records Voice Memo
    Flutter App (Local IP)->>FastAPI (Local/Docker): POST /upload-audio + {client_id}
    FastAPI (Local/Docker)->>Local AI (Whisper/Ollama): Transcribe (faster-whisper)
    FastAPI (Local/Docker)->>Local AI (Whisper/Ollama): Extract JSON (Ollama Llama3/Phi3)
    Local AI (Whisper/Ollama)-->>FastAPI (Local/Docker): Structured Data
    FastAPI (Local/Docker)->>Postgres DB (Docker): Save to client_context (using strict client_id)
    FastAPI (Local/Docker)->>OpenSearch (Docker): Log inference metrics
    end

    rect rgb(230, 255, 230)
    Note over FastAPI (Local/Docker), Local AI (Whisper/Ollama): Phase 2: Trigger & Generate (e.g. Daily Cron)
    FastAPI (Local/Docker)->>Postgres DB (Docker): Fetch clients needing reviews
    Postgres DB (Docker)-->>FastAPI (Local/Docker): Returns Financials + Context Tags
    FastAPI (Local/Docker)->>Local AI (Whisper/Ollama): Inject into System Prompt
    Local AI (Whisper/Ollama)-->>FastAPI (Local/Docker): Drafted Email (Ollama Llama3/Mistral)
    FastAPI (Local/Docker)->>Postgres DB (Docker): Save to message_drafts
    end

    rect rgb(255, 240, 230)
    Note over Advisor, Postgres DB (Docker): Phase 3: Human-in-the-Loop Review
    Advisor->>Flutter App (Local IP): Opens "Pending Drafts"
    Flutter App (Local IP)->>Postgres DB (Docker): Fetch Drafts
    Advisor->>Flutter App (Local IP): Approves Draft -> Opens native Mail app
    Flutter App (Local IP)->>FastAPI (Local/Docker): Mark as Sent
    end


3. Entity Relationship Diagram (ERD)
This defines the local PostgreSQL database schema. It strictly separates financial "hard numbers" from the AI-extracted "soft context" to prevent hallucination.
erDiagram
    ADVISORS ||--o{ CLIENTS : manages
    CLIENTS ||--|| FINANCIAL_PROFILES : has
    CLIENTS ||--o{ CLIENT_CONTEXT : generates
    CLIENTS ||--o{ INTERACTIONS : records
    CLIENTS ||--o{ MESSAGE_DRAFTS : receives

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
        string category "e.g. personal_interest"
        string content "e.g. Loves cricket"
        uuid source_interaction_id FK
    }

    INTERACTIONS {
        uuid id PK
        uuid client_id FK
        string type "voice_memo"
        text raw_transcript
        timestamp created_at
    }

    MESSAGE_DRAFTS {
        uuid id PK
        uuid client_id FK
        string trigger_type
        text generated_content
        string status "pending, sent"
    }


4. Mobile UI Blueprint (Flutter)
The mobile app is strictly task-oriented with a Bottom Navigation Bar containing two tabs.
Tab 1: Capture (Data In)
Element 1 (Critical): Searchable Client Dropdown. The user must select a client before recording is allowed.
Element 2: Giant "Hold to Record" button (disabled until a client is selected).
Feedback: Audio wave animation and timer.
Action: Submits audio file AND client_id parameter via HTTP POST form-data to http://192.168.x.x:8000/upload-audio.
Tab 2: Inbox (Data Out & Review)
List View: Shows pending message_drafts (Client Name, Trigger Type).
Detail View: Shows the AI's generated draft and a read-only banner of the Context Tags the AI used to write it.
Action: "Approve & Send" button triggers url_launcher to open mailto: on the device, and marks the draft as sent in the DB.
5. Local Infrastructure (Docker Setup)
To run the database, telemetry, and local LLMs without polluting your laptop, we use Docker Compose.
docker-compose.yml
version: '3.8'

services:
  # 1. The Source of Truth
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: localpassword
      POSTGRES_DB: advisor_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  # 2. LLM Telemetry & Logging
  opensearch-node:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - OPENSEARCH_INITIAL_ADMIN_PASSWORD=ComplexPassword123!
    ports:
      - "9200:9200"
    volumes:
      - osdata:/usr/share/opensearch/data

  # 3. Telemetry Visual Dashboard
  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:2.11.0
    ports:
      - "5601:5601"
    environment:
      OPENSEARCH_HOSTS: '["https://opensearch-node:9200"]'
    depends_on:
      - opensearch-node

  # 4. Local AI Engine (Ollama)
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  pgdata:
  osdata:
  ollama_data:


FastAPI Backend Dockerfile
For Sprint 5, to package your Python app:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Ensure faster-whisper and ollama-python are in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Expose port 8000 to the local network
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


6. Iteration Plan & Timeline (10 Weeks)
gantt
    title AI Financial Advisor Delivery Timeline (10 Weeks)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d
    
    section Sprint 1: Data In
    Docker: DB & Ollama Setup      :crit, s1_1, 2026-03-23, 3d
    FastAPI Local Whisper Setup    :s1_2, after s1_1, 4d
    Ollama Extraction Integration  :s1_3, after s1_2, 3d
    Flutter Audio Capture + UI Picker:s1_4, after s1_1, 6d
    
    section Sprint 2: Data Out
    Context Injection Logic        :crit, s2_1, 2026-04-06, 4d
    Docker: OpenSearch Setup       :s2_2, after s2_1, 3d
    Prompt Engineering (Local AI)  :s2_3, after s2_2, 5d
    Local Python Scheduler Setup   :s2_4, after s2_2, 3d
    
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


