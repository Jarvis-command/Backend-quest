"""Retry policy with exponential backoff + jitter."""
from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.database import async_session
from app.repositories import job_record_repository as job_repo

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    jitter_pct: float = 0.20  # ±20%
    timeout_s: float = 60.0   # per-attempt cap


class PermanentError(Exception):
    """Signal that retrying won't help. Goes straight to DLQ."""


def _backoff_delay(attempts: int, policy: RetryPolicy) -> float:
    """Exponential: 1s, 2s, 4s, 8s, ... capped, with jitter."""
    base = min(policy.base_delay_s * (2 ** (attempts - 1)), policy.max_delay_s)
    jitter = base * policy.jitter_pct * (random.random() * 2 - 1)
    return max(0.1, base + jitter)


async def run_with_policy(
    job_id: UUID,
    work: Callable[[], Awaitable[None]],
    policy: RetryPolicy,
) -> None:
    """Run `work` with retries and timeout. Updates job_record on each attempt."""

    while True:
        async with async_session() as db:
            record = await job_repo.get_by_id(db, job_id)
            if record is None:
                logger.error("Job %s vanished from DB; aborting", job_id)
                return
            if record.status in {"succeeded", "dead_letter", "cancelled"}:
                return  # already done — idempotent return
            await job_repo.mark_running(db, record)
            await db.commit()

        try:
            await asyncio.wait_for(work(), timeout=policy.timeout_s)

        except asyncio.CancelledError:
            logger.info("Job %s cancelled", job_id)
            raise

        except PermanentError as exc:
            async with async_session() as db:
                record = await job_repo.get_by_id(db, job_id)
                await job_repo.mark_dead_letter(db, record, error=str(exc))
                await db.commit()
            logger.error("Job %s → DLQ (permanent): %s", job_id, exc)
            return

        except (asyncio.TimeoutError, Exception) as exc:
            async with async_session() as db:
                record = await job_repo.get_by_id(db, job_id)
                if record.attempts >= policy.max_attempts:
                    await job_repo.mark_dead_letter(db, record, error=str(exc))
                    await db.commit()
                    logger.error(
                        "Job %s → DLQ (exhausted after %d attempts): %s",
                        job_id, record.attempts, exc,
                    )
                    return
                delay = _backoff_delay(record.attempts, policy)
                next_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                await job_repo.mark_retrying(db, record, error=str(exc), next_retry_at=next_at)
                await db.commit()
                logger.warning(
                    "Job %s attempt %d failed: %s — retrying in %.2fs",
                    job_id, record.attempts, exc, delay,
                )
            await asyncio.sleep(delay)
            continue

        else:
            async with async_session() as db:
                record = await job_repo.get_by_id(db, job_id)
                await job_repo.mark_succeeded(db, record)
                await db.commit()
            logger.info("Job %s succeeded after %d attempt(s)", job_id, record.attempts)
            return