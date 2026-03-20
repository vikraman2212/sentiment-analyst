from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str  # Required — set in .env or environment

    # App
    LOG_LEVEL: str = "INFO"

    # ML
    WHISPER_MODEL: str = "base.en"  # faster-whisper model size

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"  # Local Ollama server
    OLLAMA_MODEL: str = "llama3.2"  # Model to use for JSON extraction


settings = Settings()
