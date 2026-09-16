"""Unit of Work — transaction boundary owned by services."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class UnitOfWork:
    """Wrap a session in an explicit transaction boundary.

    Usage:
        async with uow:
            await repo.do_thing(uow.session, ...)
            await repo.do_other(uow.session, ...)
            uow.publish_after_commit(send_notification, args=(...))
        # commits here on clean exit, rolls back on exception
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self._after_commit: list[tuple[Callable[..., Awaitable], tuple, dict]] = []

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc is None:
                await self.session.commit()
                await self._run_after_commit_hooks()
            else:
                await self.session.rollback()
                logger.warning("UoW rolled back: %s", exc)
        finally:
            await self.session.close()
            self.session = None
            self._after_commit.clear()

    def publish_after_commit(
        self,
        coro_factory: Callable[..., Awaitable],
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> None:
        """Register a coroutine to run after a successful commit.

        Used for: scheduling workers, sending notifications, calling external APIs —
        anything that should happen IFF the DB transaction succeeded.
        """
        self._after_commit.append((coro_factory, args, kwargs or {}))

    async def _run_after_commit_hooks(self) -> None:
        for fn, args, kwargs in self._after_commit:
            try:
                await fn(*args, **kwargs)
            except Exception:
                # Hook failures don't roll back — DB is already committed.
                # In production you'd write to an outbox table for retry (Module 28).
                logger.exception("after_commit hook failed: %s", fn.__name__)
