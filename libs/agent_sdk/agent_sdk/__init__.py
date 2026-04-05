"""Agent SDK — shared infrastructure for autonomous agents.

Import from this module to access all stable public API symbols.
Do not import from internal sub-modules (core.*, providers.*) directly —
those are subject to change between minor versions.
"""

from agent_sdk.agents.generation import (
    GenerationAgent,
    GenerationWorker,
    IClientSource,
    IContextAssembler,
    IDraftWriter,
    PromptContext,
    SchedulerService,
)
from agent_sdk.audit.logger import AbstractAuditLogger, OpenSearchAuditLogger
from agent_sdk.audit.models import LLMAuditEvent
from agent_sdk.audit.noop import NoOpAuditLogger
from agent_sdk.config import AgentSDKConfig
from agent_sdk.core.contracts import AgentResult, AgentTrigger, BaseAgent
from agent_sdk.core.exceptions import (
    ConflictError,
    ExtractionError,
    GenerationError,
    LLMProviderError,
    NotFoundError,
)
from agent_sdk.core.llm_provider import LLMProvider, LLMResult
from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.core.session import IAsyncSession, ISessionFactory
from agent_sdk.orchestration.scheduler import BaseSchedulerPublisher
from agent_sdk.orchestration.worker import BaseQueueWorker

__version__ = "0.1.0"

__all__ = [
    # Base agent contract
    "BaseAgent",
    "AgentTrigger",
    "AgentResult",
    # Generation agent
    "GenerationAgent",
    "GenerationWorker",
    "SchedulerService",
    "IContextAssembler",
    "IDraftWriter",
    "IClientSource",
    "PromptContext",
    # Orchestration
    "BaseQueueWorker",
    "BaseSchedulerPublisher",
    # LLM
    "LLMProvider",
    "LLMResult",
    # Queue
    "MessageQueue",
    "GenerationMessage",
    # Session
    "IAsyncSession",
    "ISessionFactory",
    # Config
    "AgentSDKConfig",
    # Audit
    "LLMAuditEvent",
    "AbstractAuditLogger",
    "OpenSearchAuditLogger",
    "NoOpAuditLogger",
    # Exceptions
    "NotFoundError",
    "ConflictError",
    "ExtractionError",
    "LLMProviderError",
    "GenerationError",
]
