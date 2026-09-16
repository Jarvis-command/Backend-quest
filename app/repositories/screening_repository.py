"""Database access for the Screening resource. The ONLY place we write SQL for screenings."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import Screening


async def create(db: AsyncSession, **fields) -> Screening:
    """Insert a new screening and return the persisted instance."""
    screening = Screening(**fields)
    db.add(screening)
    await db.flush()
    await db.refresh(screening)
    return screening


async def get_by_id(db: AsyncSession, id: UUID) -> Screening | None:
    return await db.get(Screening, id)


async def list_filtered(
    db: AsyncSession,
    *,
    site_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Screening]:
    stmt = select(Screening).order_by(Screening.created_at.desc()).limit(limit)
    if site_id is not None:
        stmt = stmt.where(Screening.site_id == site_id)
    if status is not None:
        stmt = stmt.where(Screening.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_status(
    db,
    screening,
    *,
    status,
    eligibility_result=None,
    failed_criteria=None,
):
    screening.status = status
    if eligibility_result is not None:
        screening.eligibility_result = eligibility_result
    if failed_criteria is not None:
        screening.failed_criteria = failed_criteria
    await db.flush()
    await db.refresh(screening)
    return screening


async def mark_enrolled(
    db,
    screening,
    *,
    subject_id: str,
):
    screening.status = "enrolled"
    screening.subject_id = subject_id
    # `enrolled_at` was added in the Module 07 exercise; if you skipped it,
    # delete this line and add the column when you tackle that exercise.
    screening.enrolled_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(screening)
    return screening


# async def update_eligibility(
#     db: AsyncSession,
#     screening_id:Screening,
#     *,
#     eligible: bool,
#     failed_criteria: list[str]
#     )-> Screening:
#     return


async def delete(db, screening):
    await db.delete(screening)
    await db.flush()
