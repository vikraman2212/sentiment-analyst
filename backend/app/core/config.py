from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str  # Required — set in .env or environment

    # App
    LOG_LEVEL: str = "INFO"

    # ML
    WHISPER_MODEL: str = "base.en"  # faster-whisper model size

    # LLM provider routing
    LLM_PROVIDER: str = "ollama"  # "ollama" | future: "openai", "anthropic"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"  # Local Ollama server
    OLLAMA_EXTRACTION_MODEL: str = "llama3.2"  # Model for JSON extraction pipeline
    OLLAMA_GENERATION_MODEL: str = "llama3.2"  # Model for email generation pipeline
    OLLAMA_TIMEOUT_SECONDS: int = 120  # Per-request httpx timeout

    # OpenSearch
    OPENSEARCH_URL: str = "http://localhost:9200"  # Local Compose service

    # MinIO / S3-compatible blob store
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "audio-uploads"
    MINIO_PRESIGN_EXPIRY: int = 300  # seconds

    # Scheduler
    SCHEDULER_TIMEZONE: str = "Australia/Sydney"
    SCHEDULER_HOUR: int = 8  # 24-hour clock; when to fire the daily generation job
    SCHEDULER_SECRET: str = "change-me-in-production"  # X-Scheduler-Secret header

    # MinIO event notifications
    # X-Minio-Webhook-Secret / Authorization header
    MINIO_WEBHOOK_SECRET: str = "change-me-in-production"

    # Message queue
    QUEUE_BACKEND: str = "inmemory"  # "inmemory" | "redis"
    REDIS_URL: str = "redis://localhost:6379"

    # OpenTelemetry
    OTEL_ENABLED: bool = False  # Set True to activate tracing and metrics export
    OTEL_SERVICE_NAME: str = "sentiment-analyst-backend"
    OTEL_ENDPOINT: str = "http://localhost:4318"  # OTLP HTTP collector endpoint
    OTEL_LLM_CAPTURE_PROMPTS: bool = False
    # Set True to include prompt text in LLM spans (disabled by default)

    # Prompt overrides — set to a non-empty string to replace the built-in
    # prompt at runtime
    EXTRACTION_PROMPT_OVERRIDE: str = ""
    GENERATION_PROMPT_OVERRIDE: str = ""

    # Ollama retry / backoff
    OLLAMA_MAX_RETRIES: int = 3  # Maximum retry attempts per LLM request
    OLLAMA_BACKOFF_FACTOR: float = 2.0  # Multiplier: waits 1s, 2s, 4s, …


settings = Settings()  # type: ignore[call-arg]
