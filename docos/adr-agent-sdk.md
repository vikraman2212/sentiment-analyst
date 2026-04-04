# ADR: Agent SDK — Shared Infrastructure Library

**Status:** Accepted  
**Date:** 2026-04-03  
**Relates to:** Epic #86 — Decouple autonomous agents from the backend; Issue #90

---

## Context

The current backend couples orchestration, prompts, LLM selection, post-processing, and
persistence into a single generation service. Extracting autonomous agents as standalone packages
requires a shared, stable infrastructure layer so each agent can:

- depend on common primitives without importing backend-internal modules
- own its context assembly, prompts, provider choice, and output tables
- run independently of the backend process

---

## Decision

Create `libs/agent_sdk/` as a standalone Python package that provides the common infrastructure
every autonomous agent can reuse.

---

## In Scope

| Artifact                            | Description                                                                      |
| ----------------------------------- | -------------------------------------------------------------------------------- |
| `BaseAgent` contract                | Abstract base class every agent must subclass — defines `run(trigger) -> result` |
| `AgentTrigger` / `AgentResult`      | Generic dataclasses for queue-driven work                                        |
| `LLMProvider` Protocol              | Provider-agnostic interface for LLM completion calls                             |
| `LLMResult`                         | Completion output dataclass (response, tokens, latency)                          |
| `MessageQueue` Protocol             | Queue-agnostic interface for publish / consume / ack                             |
| `GenerationMessage`                 | Queue message envelope with W3C trace context and schema version                 |
| `ISessionFactory` / `IAsyncSession` | Read-only DB session protocols so agents can read shared core data               |
| `AgentSDKConfig`                    | Pydantic-settings model for LLM, queue, DB, and telemetry knobs                  |
| `LLMAuditEvent`                     | Structured audit event dataclass                                                 |
| `AbstractAuditLogger`               | Protocol for audit logging — pluggable per deployment                            |
| `OpenSearchAuditLogger`             | Concrete audit logger writing to OpenSearch                                      |
| `NoOpAuditLogger`                   | Audit logger no-op implementation for testing                                    |
| `OllamaProvider`                    | Default `LLMProvider` implementation backed by local Ollama                      |
| `InMemoryQueue`                     | Default `MessageQueue` backed by `asyncio.Queue`                                 |
| `RedisStreamQueue`                  | Production `MessageQueue` backed by Redis Streams                                |
| `get_llm_provider()`                | Environment-driven factory resolving the configured provider                     |
| `get_queue()`                       | Environment-driven factory resolving the configured queue backend                |

---

## Out of Scope

| Artifact                                         | Reason                                        |
| ------------------------------------------------ | --------------------------------------------- |
| Agent-specific prompts or templates              | Each agent owns its own prompts               |
| Agent-specific context assembly logic            | Business concern — not SDK infrastructure     |
| FastAPI routes, middleware, or request lifecycle | HTTP boundary stays in backend                |
| Backend database ORM models                      | SDK never imports `app.models.*`              |
| Agent-specific output / action tables            | Per-agent migration ownership                 |
| Prometheus / OpenTelemetry exporters setup       | SDK emits events; caller configures exporters |
| Whisper transcription                            | Audio pipeline stays in backend               |
| MinIO / S3 storage helpers                       | Backend-only concern                          |
| Cloud LLM providers (OpenAI, Anthropic)          | Deferred to SDK v1.1                          |

---

## Public API Contract

Agents must import exclusively from `agent_sdk.*` — never from `app.*`.

```python
from agent_sdk import (
    BaseAgent,
    AgentTrigger,
    AgentResult,
    LLMProvider,
    LLMResult,
    MessageQueue,
    GenerationMessage,
    ISessionFactory,
    AgentSDKConfig,
    LLMAuditEvent,
    AbstractAuditLogger,
    OpenSearchAuditLogger,
    NoOpAuditLogger,
)
from agent_sdk.dependencies.factories import get_llm_provider, get_queue
from agent_sdk.providers.llm.ollama import OllamaProvider
from agent_sdk.providers.queue.inmemory import InMemoryQueue
from agent_sdk.providers.queue.redis import RedisStreamQueue
```

Internal SDK modules (`agent_sdk.core.*`, `agent_sdk.providers.*`) are not part of the
public API and may change between minor versions.

---

## Key Constraints

1. SDK must be `async`-first — no blocking calls anywhere in the library.
2. SDK must never import from `app.*` (backend internals).
3. SDK must never log PII (email, name, financial amounts) at any level.
4. Telemetry is pluggable — SDK records nothing by default unless a logger is injected.
5. The queue `GenerationMessage` carries a `schema_version` field for forward compatibility.
6. All public functions and classes carry full type annotations and Google-style docstrings.

---

## Consequences

- Backend continues to own all API routes, ORM models, repositories, and Alembic migrations.
- Backend imports SDK contracts for the LLM and queue boundaries (incremental, tracked in #92).
- Each autonomous agent owns its `pyproject.toml`, Alembic migrations, prompts, and output schemas.
- The `email_agent` (#87) will be the first consumer of the SDK and validates all contracts.

---

## Implementation Order

See [plan-agentSdk.prompt.md](../plan-agentSdk.prompt.md) for the full sequential checklist.
