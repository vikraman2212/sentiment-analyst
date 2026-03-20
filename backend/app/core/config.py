from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = (
        "postgresql+psycopg://admin:localpassword@localhost:5432/advisor_db"
    )
    LOG_LEVEL: str = "INFO"  # Override via LOG_LEVEL env var in production
    WHISPER_MODEL: str = "base.en"  # faster-whisper model size; override via env var


settings = Settings()
