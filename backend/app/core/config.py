from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str  # Required — set in .env or environment

    # App
    LOG_LEVEL: str = "INFO"

    # ML
    WHISPER_MODEL: str = "base.en"  # faster-whisper model size


settings = Settings()
