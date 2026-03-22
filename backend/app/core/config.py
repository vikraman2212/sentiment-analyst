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

    # Message queue
    QUEUE_BACKEND: str = "inmemory"  # "inmemory" | "redis"
    REDIS_URL: str = "redis://localhost:6379"


settings = Settings()
