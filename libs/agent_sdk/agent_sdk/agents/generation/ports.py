"""Protocol interfaces (ports) for the generation agent's external dependencies.

These protocols decouple the agent logic from concrete SQLAlchemy models and
backend service implementations.  The backend provides adaptors that satisfy
these protocols; tests supply lightweight fakes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class PromptContext:
    """Minimal context payload the generation agent needs to call the LLM.

    Attributes:
        prompt_block: Formatted markdown assembled from the client's financial
            profile and context tags.  Passed verbatim as the user message.
        client_name: Display name used only for structured log output.
    """

    prompt_block: str
    client_name: str


@runtime_checkable
class IContextAssembler(Protocol):
    """Assembles a prompt-ready context block for a given client."""

    async def assemble(self, client_id: uuid.UUID) -> PromptContext:
        """Fetch and format the client's context as a prompt block.

        Args:
            client_id: UUID of the target client.

        Returns:
            PromptContext containing the formatted prompt block and client name.

        Raises:
            NotFoundError: If the client does not exist.
        """
        ...


@runtime_checkable
class IDraftWriter(Protocol):
    """Persists and manages generated message drafts."""

    async def find_pending_draft(self, client_id: uuid.UUID) -> uuid.UUID | None:
        """Return the ID of an existing pending draft for this client, or None.

        Args:
            client_id: UUID of the target client.

        Returns:
            Draft UUID if a pending draft exists, else None.
        """
        ...

    async def create_draft(
        self,
        client_id: uuid.UUID,
        trigger_type: str,
        content: str,
    ) -> uuid.UUID:
        """Persist a new draft and return its UUID.

        Args:
            client_id: UUID of the target client.
            trigger_type: Label for what triggered this draft.
            content: The generated email body text.

        Returns:
            UUID of the newly created draft.
        """
        ...

    async def delete_draft(self, draft_id: uuid.UUID) -> None:
        """Delete a draft by ID.

        Args:
            draft_id: UUID of the draft to delete.
        """
        ...


@runtime_checkable
class IClientSource(Protocol):
    """Provides the set of (client_id, advisor_id) pairs eligible for generation."""

    async def get_eligible_clients(
        self, session: Any
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Return pairs of (client_id, advisor_id) that need a draft generated.

        Args:
            session: Active async DB session from the SDK session factory.

        Returns:
            List of (client_id, advisor_id) tuples.  May be empty if no
            clients are currently eligible.
        """
        ...
