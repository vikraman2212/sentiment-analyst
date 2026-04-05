"""Agent SDK configuration model.

All settings are read from environment variables or a ``.env`` file.
Agents instantiate ``AgentSDKConfig()`` directly — the SDK does not
maintain a global singleton so each agent process controls its own config.

Example::

    from agent_sdk.config import AgentSDKConfig

    config = AgentSDKConfig()
    print(config.OLLAMA_BASE_URL)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSDKConfig(BaseSettings):
    """Pydantic-settings model for all SDK infrastructure knobs.

    Attributes:
        DATABASE_URL: Async-compatible PostgreSQL URL
            (e.g. ``postgresql+psycopg://user:pass@host:5432/db``).
        LLM_PROVIDER: Which LLM backend to use. Currently only ``"ollama"``
            is supported; ``"openai"`` and ``"anthropic"`` are planned for v1.1.
        OLLAMA_BASE_URL: Base URL of the local Ollama server.
        OLLAMA_TIMEOUT_SECONDS: Per-request HTTP timeout for Ollama calls.
        OLLAMA_MAX_RETRIES: Number of retry attempts on transient HTTP errors.
        OLLAMA_BACKOFF_FACTOR: Exponential backoff multiplier between retries.
        QUEUE_BACKEND: Which queue backend to use — ``"inmemory"`` or ``"redis"``.
        REDIS_URL: Redis connection URL used when ``QUEUE_BACKEND="redis"``.
        OPENSEARCH_URL: OpenSearch base URL for the audit logger.
        OTEL_ENABLED: Enable OpenTelemetry trace export when ``True``.
        OTEL_SERVICE_NAME: Service name tag attached to all spans.
        OTEL_ENDPOINT: OTLP HTTP collector endpoint.
        OTEL_LLM_CAPTURE_PROMPTS: Include raw prompt text in LLM spans when
            ``True``. Disabled by default to avoid PII leakage.
        LOG_LEVEL: structlog minimum log level (``"INFO"``, ``"DEBUG"``, etc.).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+psycopg://sentiment:sentiment@localhost:5434/sentiment"

    # LLM provider routing
    LLM_PROVIDER: str = "ollama"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT_SECONDS: int = 120
    OLLAMA_MAX_RETRIES: int = 3
    OLLAMA_BACKOFF_FACTOR: float = 2.0

    # Message queue
    QUEUE_BACKEND: str = "inmemory"
    REDIS_URL: str = "redis://localhost:6379"

    # OpenSearch (for audit logging)
    OPENSEARCH_URL: str = "http://localhost:9200"

    # OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "agent-sdk"
    OTEL_ENDPOINT: str = "http://localhost:4318"
    OTEL_LLM_CAPTURE_PROMPTS: bool = False

    # LLM model identifiers
    OLLAMA_GENERATION_MODEL: str = "llama3.2"

    # Prompt overrides (empty = use built-in default)
    GENERATION_PROMPT_OVERRIDE: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"
