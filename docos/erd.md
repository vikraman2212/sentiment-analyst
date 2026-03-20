Engineering Requirements Document (ERD)
Project: AI Financial Advisor MVP (Local-First)
Author: Solo Developer
Date: March 2026
1. Technology Stack Specifications
1.1. Mobile Client (Frontend)
Framework: Flutter (Dart 3.x)
State Management: Provider or Riverpod (minimal global state required).
Core Packages:
record / flutter_sound: For microphone access and .m4a/.wav recording.
path_provider: For temporary local storage of audio files before upload.
http: For REST API communication.
url_launcher: For invoking native OS email clients (mailto:).
1.2. API Gateway & Middleware (Backend)
Framework: FastAPI (Python 3.11+)
Server: Uvicorn (Bound to 0.0.0.0:8000 to allow local Wi-Fi traffic).
ORM: SQLAlchemy 2.0 (Async) + Alembic (for database migrations).
Validation: Pydantic v2 (Crucial for API payloads and LLM JSON enforcement).
Background Tasks: APScheduler (for the daily CRON trigger).
1.3. Local AI Engine
Transcription: faster-whisper (Python library running locally).
LLM Inference: ollama-python SDK.
Extraction Model: llama3 or phi3 (Optimized for JSON output).
Generation Model: llama3 or mistral (Optimized for conversational text).
2. API Contract (RESTful Endpoints)
FastAPI will expose the following endpoints for the Flutter client and internal schedulers.
2.1. Client Management
GET /api/v1/clients
Purpose: Populates the UI dropdown before the user records audio.
Response: 200 OK
[
  {"id": "uuid-1234", "first_name": "John", "last_name": "Doe"},
  {"id": "uuid-5678", "first_name": "Jane", "last_name": "Smith"}
]


2.2. Data Ingestion (Audio Upload)
POST /api/v1/audio/upload
Purpose: Receives audio, triggers Whisper, triggers Ollama extraction, saves to DB.
Request Type: multipart/form-data
Payload:
client_id (String/UUID): The ID selected in the Flutter UI.
audio_file (Binary): The recorded audio file.
Response: 201 Created
{
  "status": "success",
  "extracted_tags_count": 3,
  "interaction_id": "uuid-9012"
}


2.3. Draft Management
GET /api/v1/drafts/pending
Purpose: Fetches drafts for the Flutter Inbox tab.
Response: 200 OK
[
  {
    "draft_id": "uuid-abcd",
    "client_name": "John Doe",
    "trigger_type": "half_yearly_review",
    "generated_content": "Hi John, looking at your $1.5M portfolio...",
    "context_used": ["Loves cricket", "Worried about mortgage"]
  }
]


POST /api/v1/drafts/{draft_id}/approve
Purpose: Marks a draft as completed once the mailto: link is clicked in Flutter.
Response: 200 OK {"status": "sent"}
3. AI Pipeline Specifications
3.1. Pipeline 1: Extraction (Audio -> JSON)
Because local LLMs can be prone to formatting errors, we must strictly enforce JSON schema extraction.
Whisper Step: faster_whisper.WhisperModel("base.en").transcribe(audio_file)
Ollama Step: * Send transcript to Ollama.
Crucial Parameter: Set format="json" in the Ollama API call.
System Prompt:"You are an expert data extractor. Read the following transcript. Extract a list of distinct personal and financial facts. You MUST return ONLY a JSON array of objects with the keys category (enum: personal_interest, financial_goal, family_event, risk_tolerance) and content (string)."
3.2. Pipeline 2: Generation (Context -> Email Text)
Triggered by the APScheduler daily at 08:00 AM.
Data Gathering: SQLAlchemy queries the FINANCIAL_PROFILES and CLIENT_CONTEXT for the target client_id.
Context Assembly (Python): Format the data into a strict Markdown block.
Ollama Step:
System Prompt:"You are an elite financial advisor. Write a 4-sentence email inviting the client to a review.
CLIENT PROFILE:
Name: {first_name}
AUM: ${aum}
YTD Return: {ytd_pct}%
RECENT CONTEXT:
{context_list}
INSTRUCTIONS: Weave one piece of recent context into the financial update. Do not use exact dollar amounts. Be warm and professional. Output ONLY the email body."
4. Telemetry & Auditing Implementation
All AI operations must be logged to the local OpenSearch cluster.
Implementation: Create a Python dependency/middleware in FastAPI log_llm_transaction().
Trigger: Called asynchronously after every Ollama invocation.
Payload to OpenSearch (POST /llm-audits/_doc):
{
  "timestamp": "2026-03-20T14:00:00Z",
  "pipeline": "extraction",
  "client_id": "uuid-1234",
  "model": "llama3",
  "prompt_tokens": 450,
  "completion_tokens": 45,
  "latency_ms": 12500,
  "status": "success",
  "raw_prompt": "...[full text]...",
  "raw_response": "...[full text]..."
}


5. Security & Networking Constraints
Since this is a Local-First architecture designed to run on a home/office Wi-Fi network:
CORS (Cross-Origin Resource Sharing): * FastAPI must have CORSMiddleware configured to allow * (or the specific local IP range) so the Flutter app can make requests without browser-level blocking.
Network Binding: * Running uvicorn main:app binds to localhost (127.0.0.1) by default, meaning the phone cannot see it.
Requirement: Uvicorn must be started with --host 0.0.0.0 to listen on all network interfaces.
App Configuration: * The Flutter app should implement a settings screen (or a .env file for dev) where the advisor can input their laptop's current IPv4 address (e.g., 192.168.1.50).
6. Database Migrations (Alembic)
Initial setup must include an Alembic migration script to construct the 5 tables defined in the ERD.
Foreign keys MUST have ON DELETE CASCADE configured to ensure that if a CLIENT is deleted, their CLIENT_CONTEXT, INTERACTIONS, and MESSAGE_DRAFTS are also purged to maintain database hygiene.
