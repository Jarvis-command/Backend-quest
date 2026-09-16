from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_record import JobRecord


async def get_or_create(db, *, idempotency_key: str, **fields) -> tuple[JobRecord, bool]:
    """Idempotent: if a record exists for this key, return it; otherwise create."""
    result = await db.execute(select(JobRecord).where(JobRecord.idempotency_key == idempotency_key))
    existing = result.scalars().first()
    if existing:
        return existing, False
    record = JobRecord(idempotency_key=idempotency_key, **fields)
    db.add(record)
    await db.flush()
    return record, True


async def mark_running(db, record: JobRecord) -> None:
    record.status = "running"
    record.attempts += 1
    await db.flush()


async def mark_succeeded(db, record: JobRecord) -> None:
    record.status = "succeeded"
    record.last_error = None
    await db.flush()


async def mark_retrying(db, record: JobRecord, *, error: str, next_retry_at: datetime) -> None:
    record.status = "queued"
    record.last_error = error
    record.last_error_at = datetime.now(timezone.utc)
    record.next_retry_at = next_retry_at
    await db.flush()


async def mark_dead_letter(db, record: JobRecord, *, error: str) -> None:
    record.status = "dead_letter"
    record.last_error = error
    record.last_error_at = datetime.now(timezone.utc)
    await db.flush()


async def get_by_id(db, job_id: UUID) -> JobRecord | None:
    return await db.get(JobRecord, job_id)