"""Background task runner for screening pipeline jobs.

Owns:
  - A ThreadPoolExecutor for CPU/sync-library work
  - A registry of running tasks (so we can cancel)

Does NOT own:
  - State machine (the service does)
  - Decisions about what to run (the service hands it work)
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

logger = logging.getLogger(__name__)


class BackgroundTaskRunner:
    """Schedule async coroutines as background tasks. Track them so we can cancel."""

    def __init__(self, executor, *, max_concurrency:int =10):
        self._executor = executor
        self._tasks: dict[UUID, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Expose the thread pool for blocking-call escape hatches."""
        return self._executor

    def submit(self, key: UUID, coro_factory: Callable[[], Awaitable[None]]) -> None:
        """Start a background coroutine, keyed for cancellation."""
        if key in self._tasks and not self._tasks[key].done():
            logger.warning("Task %s already running, ignoring duplicate submit", key)
            return
        async def runner():
            async with self._semaphore:
                await coro_factory()
        self._tasks[key] = asyncio.create_task(runner())

    def cancel(self, key: UUID) -> bool:
        task = self._tasks.get(key)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def shutdown(self, timeout: float = 10.0) -> None:
        """Cancel all running tasks and wait for them to finish."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks.values(), timeout=timeout)
        self._executor.shutdown(wait=False)