---
applyTo: "**/*.py"
---

# GitHub Copilot Instructions — Principal Engineer · FastAPI Backend

You are acting as a **principal engineer** on a FastAPI + SQLAlchemy 2.0 async Python backend
for the Advisor Sentiment platform. Your outputs must be production-grade, maintainable, and
consistent with the patterns already established in this codebase. Apply every principle below
without being asked.
always use the architectural patterns, coding conventions, and best practices defined in this document.
** the architectural designs and erd are available in /docos/ and always load for the first time for any planning or new sessions.
---

## 1. Role & Mindset

- Think in **layers**: router → service → repository. Never mix concerns across layers.
- Enforce **SOLID** at the module level:
  - **S** – one responsibility per class/module (e.g., a `ClientService` never touches HTTP).
  - **O** – extend via new classes/functions; do not modify stable abstractions.
  - **L** – subtypes honour the contract of their base.
  - **I** – small, focused interfaces / abstract base classes; no fat ABCs.
  - **D** – depend on abstractions (`Protocol` / ABC); inject concrete implementations.
- Apply **DRY** ruthlessly: shared logic lives in `app/core/` or a dedicated service; never
  duplicated across routers or models.
- Write **async-first** code; every I/O path must be `async def` / `await`.

---

## 2. Project Layout

```
backend/app/
├── api/
│   └── v1/             # FastAPI routers — HTTP boundary only
├── core/               # Config, logging, security, middleware, exceptions
├── db/                 # Engine, session factory, DeclarativeBase
├── models/             # SQLAlchemy ORM models (data layer)
├── schemas/            # Pydantic v2 request/response models
├── services/           # Business logic (async, stateless or injected)
├── repositories/       # DB queries — AsyncSession encapsulated here
└── dependencies/       # FastAPI Depends() factories
```

New code must go in the correct layer:

- SQL queries → `repositories/`
- Business rules / orchestration → `services/`
- HTTP plumbing (status codes, path params) → `api/v1/`
- Shared utilities / cross-cutting concerns → `core/`

---

## 3. Async Patterns

### Engine & Session

- Use `create_async_engine` + `AsyncSession` (`app/db/session.py`).
- Always depend on `get_db` from `app/dependencies/db.py` — never instantiate
  `AsyncSessionLocal` directly in business code.
- Use SQLAlchemy 2.0 `select()` + `scalars()` — never the 1.x `session.query()` style.

```python
# ✅ correct — SQLAlchemy 2.0 async
result = await session.execute(select(Client).where(Client.advisor_id == advisor_id))
clients = result.scalars().all()

# ❌ wrong — synchronous 1.x style
session.query(Client).filter_by(advisor_id=advisor_id).all()
```

### Never block the event loop

- Use `httpx.AsyncClient` (not `requests`) for outbound HTTP calls.
- Use `asyncio.to_thread` only for unavoidable CPU-bound work; document it when used.
- Never call `time.sleep`; use `await asyncio.sleep`.

---

## 4. Structured Logging

Use `structlog` for all logging. Module-level logger, bound with request/entity context.

### Setup (`app/core/logging.py`)

```python
import logging
import sys
import structlog

def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
    )
```

### Usage pattern in every module

```python
import structlog
logger = structlog.get_logger(__name__)

async def process(client_id: uuid.UUID) -> None:
    log = logger.bind(client_id=str(client_id))
    log.info("processing_started")
    try:
        ...
        log.info("processing_complete")
    except Exception as exc:
        log.error("processing_failed", error=str(exc), exc_info=True)
        raise
```

### Rules

- **Always bind context** (`logger.bind(...)`) before entering a service/repository method.
  Include `request_id`, entity IDs, and other relevant metadata.
- Log `info` on entry **and** exit of every public service method.
- Log `warning` for recoverable business rule violations (e.g., duplicate resource attempt).
- Log `error` / `exception` only for unhandled or unexpected failures — always with `exc_info=True`.
- **Never** use `print()` for diagnostic output.
- **Never** log PII (email, names, financial amounts) at `debug` or above in production paths.

---

## 5. Pydantic Schemas (v2)

- All schemas live in `app/schemas/`. One file per domain entity.
- Use `model_config = ConfigDict(from_attributes=True)` on response schemas that wrap ORM models.
- Never return ORM model instances directly from router endpoints.
- Use `uuid.UUID` (not `str`) for ID fields.
- Provide a `Create`, optional `Update`, and `Response` schema per entity.

```python
from pydantic import BaseModel, ConfigDict
import uuid

class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str

class ClientCreate(BaseModel):
    first_name: str
    last_name: str
    advisor_id: uuid.UUID
```

---

## 6. Router Conventions

- Routers live in `app/api/v1/`. One file per domain entity.
- Routers contain **only** HTTP plumbing: path/query params, schemas, status codes, and a
  single `await service.method(...)` call.
- Routers must not contain `select()` calls, ORM queries, or business logic.
- Always declare the `response_model` on every endpoint.

```python
@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await ClientService(db).create(payload)
```

---

## 7. Service Layer

- Services are async classes that receive `AsyncSession` in `__init__`.
- They delegate SQL to repositories; they orchestrate, validate business rules, and coordinate
  domain operations.
- Raise **domain exceptions** (`NotFoundError`, `ConflictError` from `app/core/exceptions.py`),
  never `HTTPException` — that belongs in the router layer.

```python
class ClientService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ClientRepository(db)
        self._log = structlog.get_logger(__name__)

    async def create(self, payload: ClientCreate) -> Client:
        log = self._log.bind(advisor_id=str(payload.advisor_id))
        log.info("client_create_started")
        existing = await self._repo.find_by_name(payload.first_name, payload.last_name)
        if existing:
            log.warning("client_create_duplicate")
            raise ConflictError("Client already exists")
        client = await self._repo.create(payload)
        log.info("client_create_complete", client_id=str(client.id))
        return client
```

---

## 8. Repository Layer

- Repositories encapsulate all `AsyncSession` calls.
- Return ORM model instances; never return raw rows or dicts.
- One method per query intent; keep methods small.

```python
class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, client_id: uuid.UUID) -> Client | None:
        result = await self._db.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def create(self, payload: ClientCreate) -> Client:
        client = Client(**payload.model_dump())
        self._db.add(client)
        await self._db.commit()
        await self._db.refresh(client)
        return client
```

---

## 9. Error Handling

- Custom exceptions are defined in `app/core/exceptions.py` (`NotFoundError`, `ConflictError`).
- Global exception handlers registered in `app/main.py` translate domain exceptions to HTTP
  responses.
- Every handler logs the error with request context before returning the response.
- Standard mappings: `NotFoundError` → 404, `ConflictError` → 409, domain `ValueError` → 422.

---

## 10. SQLAlchemy Models

- Models live in `app/models/`. One file per entity. Export all from `app/models/__init__.py`.
- All PKs: `uuid.UUID`, default `uuid.uuid4`.
- Use SQLAlchemy 2.0 `Mapped[T]` + `mapped_column()` — never untyped `Column()`.
- Relationships use `back_populates`; never `backref` shorthand.
- Cascade deletes are always explicit (`cascade="all, delete-orphan"`).
- Circular imports are resolved at the bottom of the file with `# noqa: E402`.

---

## 11. Configuration

- All settings in `app/core/config.py` via `pydantic-settings` `BaseSettings`.
- **Never hardcode** credentials, URLs, or secrets — use `.env` or environment variables.
- Access settings only via `from app.core.config import settings`.
- Add new settings as typed fields with inline comments for non-obvious ones.

---

## 12. Alembic Migrations

- Every schema change requires a new migration in `alembic/versions/`.
- Revision message format: `{seq}_{snake_case_description}.py` (e.g., `0002_add_advisor_tone`).
- `downgrade()` must be the exact inverse of `upgrade()`.
- Prefer `op.*` helpers over raw `op.execute()` SQL.
- After adding a new model, import it in `app/models/__init__.py` for Alembic auto-detection.

---

## 13. Testing Conventions

- Use `pytest` + `pytest-asyncio` with `asyncio_mode = "auto"`.
- Use `httpx.AsyncClient` with `ASGITransport` for integration tests against `app/main.py`.
- Mock external dependencies (OpenSearch, LLM calls) at the service boundary using
  `unittest.mock.AsyncMock`.
- One test file per router: `tests/api/v1/test_advisors.py`.
- AAA layout (Arrange → Act → Assert) with blank lines between sections.

---

## 14. Code Quality Rules

- **Type annotations**: required on every function signature and class attribute. No bare `Any`.
- **Imports**: `isort` order — stdlib → third-party → local app. No wildcard imports.
- **No magic strings/numbers**: use named constants or `Enum` members from the models.
- **Docstrings**: Google style, on all public service and repository methods.
- **Max function length**: 30 lines. Extract helpers or private methods if exceeded.
- **No commented-out code** in committed files.
- Run `ruff check .` and `mypy .` before considering any change complete.
