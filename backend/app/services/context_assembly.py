"""Context assembly service for the generation pipeline.

Fetches a client's financial profile and context tags, then formats them
into a deterministic markdown prompt block consumed by issue-#18's
generation pipeline.
"""

import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.client import Client
from app.models.client_context import ClientContext
from app.models.financial_profile import FinancialProfile
from app.repositories.client import ClientRepository
from app.repositories.client_context import ClientContextRepository
from app.repositories.financial_profile import FinancialProfileRepository
from app.schemas.client_context import ClientContextResponse
from app.schemas.context_assembly import AssembledContext, FinancialSummary

logger = structlog.get_logger(__name__)

_CATEGORY_LABELS: dict[str, str] = {
    "personal_interest": "Personal Interests",
    "financial_goal": "Financial Goals",
    "family_event": "Family Events",
    "risk_tolerance": "Risk Tolerance",
}
_CATEGORY_ORDER: tuple[str, ...] = (
    "personal_interest",
    "financial_goal",
    "family_event",
    "risk_tolerance",
)

_REVIEW_WINDOW_DAYS: int = 14


class ContextAssemblyService:
    """Assemble structured client context for LLM generation prompts.

    Combines hard financial facts (FinancialProfile) with soft qualitative
    notes (ClientContext tags) into a deterministic markdown block.  Missing
    data is represented as explicit "Not available" strings rather than
    raising errors, so the generation pipeline always receives a usable
    prompt.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._client_repo = ClientRepository(db)
        self._profile_repo = FinancialProfileRepository(db)
        self._context_repo = ClientContextRepository(db)
        self._log = structlog.get_logger(__name__)

    async def assemble(self, client_id: uuid.UUID) -> AssembledContext:
        """Fetch and format all context for a single client.

        Args:
            client_id: UUID of the target client.

        Returns:
            AssembledContext containing financial summary, context tags,
            and a pre-formatted prompt_block string.

        Raises:
            NotFoundError: If the client does not exist.
        """
        log = self._log.bind(client_id=str(client_id))
        log.info("context_assembly_started")

        client = await self._client_repo.get_by_id(client_id)
        if client is None:
            log.warning("context_assembly_client_not_found")
            raise NotFoundError(f"Client {client_id} not found")

        profile = await self._profile_repo.get_by_client_id(client_id)
        tags = await self._context_repo.list_by_client(client_id)

        financial_summary = _build_financial_summary(profile)
        tag_responses = [
            ClientContextResponse.model_validate(t, from_attributes=True) for t in tags
        ]
        prompt_block = self._format_prompt_block(client, financial_summary, tags)

        log.info("context_assembly_complete", tag_count=len(tags))
        return AssembledContext(
            client_id=client_id,
            client_name=f"{client.first_name} {client.last_name}",
            financial_summary=financial_summary,
            context_tags=tag_responses,
            prompt_block=prompt_block,
        )

    async def list_needing_review(
        self, advisor_id: uuid.UUID
    ) -> list[AssembledContext]:
        """Return assembled contexts for clients whose review is due within 14 days.

        Clients without a next_review_date are silently excluded.  The
        result list is ordered by next_review_date ascending.

        Args:
            advisor_id: Filter to this advisor's client roster.

        Returns:
            List of AssembledContext instances, possibly empty.
        """
        log = self._log.bind(advisor_id=str(advisor_id))
        log.info("context_assembly_review_list_started")

        cutoff = date.today() + timedelta(days=_REVIEW_WINDOW_DAYS)
        clients = await self._client_repo.list_needing_review(advisor_id, cutoff)

        if not clients:
            log.info("context_assembly_review_list_empty")
            return []

        assembled = [await self.assemble(c.id) for c in clients]
        log.info("context_assembly_review_list_complete", count=len(assembled))
        return assembled

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_prompt_block(
        self,
        client: Client,
        summary: FinancialSummary,
        tags: list[ClientContext],
    ) -> str:
        """Render a deterministic markdown block for LLM prompting.

        Financial values missing from the DB are represented as human-readable
        placeholders rather than None.  Category sections are omitted entirely
        when no tags exist for that category.

        Args:
            client: ORM Client instance for name.
            summary: FinancialSummary built from the profile (fields may be None).
            tags: All ClientContext ORM instances for this client.

        Returns:
            Multi-line markdown string suitable for embedding in a prompt.
        """
        aum_str = (
            f"${summary.total_aum:,.2f}" if summary.total_aum is not None else "Not available"
        )
        ytd_str = (
            f"{summary.ytd_return_pct:.3f}%"
            if summary.ytd_return_pct is not None
            else "Not available"
        )
        risk_str = summary.risk_profile if summary.risk_profile is not None else "Not specified"

        lines: list[str] = [
            "## Client Profile",
            f"Name: {client.first_name} {client.last_name}",
            "",
            "## Financial Summary",
            f"AUM: {aum_str}",
            f"YTD Return: {ytd_str}",
            f"Risk Profile: {risk_str}",
        ]

        # Group tags by category preserving the fixed display order
        by_category: dict[str, list[str]] = {cat: [] for cat in _CATEGORY_ORDER}
        for tag in tags:
            if tag.category in by_category:
                by_category[tag.category].append(tag.content)

        has_any_tags = any(by_category.values())
        if has_any_tags:
            lines.append("")
            lines.append("## Recent Context Notes")
            for cat in _CATEGORY_ORDER:
                contents = by_category[cat]
                if not contents:
                    continue
                lines.append(f"### {_CATEGORY_LABELS[cat]}")
                for content in contents:
                    lines.append(f"- {content}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level helper (pure function, no self dependency)
# ---------------------------------------------------------------------------

def _build_financial_summary(profile: FinancialProfile | None) -> FinancialSummary:
    """Construct a FinancialSummary, tolerating a missing profile."""
    if profile is None:
        return FinancialSummary()
    return FinancialSummary(
        total_aum=profile.total_aum,
        ytd_return_pct=profile.ytd_return_pct,
        risk_profile=profile.risk_profile,
    )
