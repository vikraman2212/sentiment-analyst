"""Read-only async session protocols for SDK consumers.

Agents that need to read shared core data (clients, financial profiles,
context tags) should accept an ``ISessionFactory`` and open sessions via
the context manager, rather than depending on backend-specific session
factories.

The SDK never creates sessions directly — the caller injects the factory.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IAsyncSession(Protocol):
    """Minimal async session interface for read-only agent access.

    Agents must treat this as read-only — they must own separate tables
    and sessions for their own output persistence.
    """

    async def execute(
        self,
        statement: Any,
        params: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a SQL statement and return the result proxy.

        Args:
            statement: A SQLAlchemy ``select()`` or other executable.
            params: Optional bound parameters.
            **kwargs: Additional keyword arguments forwarded to the driver.

        Returns:
            Result proxy with ``.scalars()``, ``.all()``, etc.
        """
        ...


@runtime_checkable
class ISessionFactory(Protocol):
    """Callable that produces a context-manager-wrapped async session.

    Agents call ``async with session_factory() as session:`` to open a
    scoped read-only session.

    Example::

        async with session_factory() as session:
            result = await session.execute(select(Client).where(...))
            clients = result.scalars().all()
    """

    def __call__(self) -> AbstractAsyncContextManager[IAsyncSession]:
        """Return an async context manager that yields an ``IAsyncSession``.

        Returns:
            Async context manager wrapping the session lifecycle.
        """
        ...
