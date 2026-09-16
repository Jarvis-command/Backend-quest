"""Dependency providers for the application.

Every dep that's used by more than one route lives here.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.database import async_session
from app.db.unit_of_work import UnitOfWork
from app.workers.task_runner import BackgroundTaskRunner


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session per request. Closes on exit."""
    async with async_session() as session:
        yield session


def get_settings() -> Settings:
    """Inject the global Settings object. Override in tests for env-specific config."""
    return settings


def get_app_state(request: Request):
    """Access the lifespan-attached app state.

    Used by sub-deps that need long-lived resources (executors, clients).
    Routes should NEVER access `request.app.state` directly — use a typed dep here.
    """
    return request.app.state


def get_request_metadata(
    x_request_source: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Synthesize a metadata dict for logging/auditing."""
    return {
        "source": x_request_source or "unknown",
        "service_version": settings.app_version,
    }

def get_task_runner(request: Request) -> BackgroundTaskRunner:
    return request.app.state.task_runner

@dataclass
class Pagination:
    limit: int
    offset: int


def get_pagination(limit: int = 50, offset: int = 0) -> Pagination:
    return Pagination(limit=min(limit, 100), offset=max(offset, 0))


def get_uow() -> UnitOfWork:
    return UnitOfWork(async_session)
