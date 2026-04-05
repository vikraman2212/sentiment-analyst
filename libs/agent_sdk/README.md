# agent_sdk

Shared infrastructure library for autonomous agents in the Advisor Sentiment platform.

## Purpose

Provides the common primitives every autonomous agent needs so agents can run independently
of the backend without importing `app.*` internals:

- **`BaseAgent`** — abstract base class defining the `run(trigger) → result` contract
- **`LLMProvider`** — protocol-based LLM abstraction (default: Ollama)
- **`MessageQueue`** — protocol-based queue abstraction (InMemory or Redis Streams)
- **`AgentSDKConfig`** — pydantic-settings model for all SDK knobs
- **`LLMAuditLogger`** — pluggable audit logging (default: OpenSearch)
- **`ISessionFactory`** — read-only DB session access for shared core data

## Installation (local editable)

```bash
# from workspace root
pip install -e libs/agent_sdk
```

## Quick start

```python
from agent_sdk import BaseAgent, AgentTrigger, AgentResult, AgentSDKConfig
from agent_sdk.dependencies.factories import get_llm_provider, get_queue


class MyAgent(BaseAgent):
    async def run(self, trigger: AgentTrigger) -> AgentResult:
        # own context assembly, prompts, and output persistence here
        return AgentResult(
            success=True,
            trigger_type=trigger.trigger_type,
            client_id=trigger.client_id,
        )
```

## Package Layout

```
agent_sdk/
├── __init__.py              Public API exports
├── config.py                AgentSDKConfig (pydantic-settings)
├── core/
│   ├── contracts.py         BaseAgent, AgentTrigger, AgentResult
│   ├── exceptions.py        Domain exceptions
│   ├── llm_provider.py      LLMProvider Protocol + LLMResult
│   ├── message_queue.py     MessageQueue Protocol + GenerationMessage
│   └── session.py           ISessionFactory / IAsyncSession protocols
├── audit/
│   ├── models.py            LLMAuditEvent dataclass
│   ├── logger.py            AbstractAuditLogger + OpenSearchAuditLogger
│   └── noop.py              NoOpAuditLogger (testing / local dev)
├── providers/
│   ├── llm/
│   │   └── ollama.py        OllamaProvider
│   └── queue/
│       ├── inmemory.py      InMemoryQueue
│       └── redis.py         RedisStreamQueue
└── dependencies/
    └── factories.py         get_llm_provider(), get_queue()
```

## Out of Scope

- Agent-specific prompts or context assembly
- FastAPI routes or middleware
- Backend ORM models (`app.models.*`)
- Prometheus / OpenTelemetry exporter setup
- Whisper transcription or MinIO storage

See `docos/adr-agent-sdk.md` for the full scope decision.

## Version Policy

SDK public API (`agent_sdk.*`) follows semver. Internal modules
(`agent_sdk.core.*`, `agent_sdk.providers.*`) may change between minor versions.
