"""Generation agent package — email draft generation pipeline.

Public API for consumers:

    from agent_sdk.agents.generation import (
        GenerationAgent,
        GenerationWorker,
        SchedulerService,
        IContextAssembler,
        IDraftWriter,
        IClientSource,
        PromptContext,
    )
"""

from agent_sdk.agents.generation.ports import (
    IClientSource,
    IContextAssembler,
    IDraftWriter,
    PromptContext,
)
from agent_sdk.agents.generation.scheduler import SchedulerService
from agent_sdk.agents.generation.service import GenerationAgent
from agent_sdk.agents.generation.worker import GenerationWorker

__all__ = [
    "GenerationAgent",
    "GenerationWorker",
    "SchedulerService",
    "IContextAssembler",
    "IDraftWriter",
    "IClientSource",
    "PromptContext",
]
