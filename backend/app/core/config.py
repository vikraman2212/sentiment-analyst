from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg://admin:localpassword@localhost:5432/advisor_db"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
