"""Business logic for screenings.

Routes orchestrate; this layer decides.
"""

import asyncio
import json
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.unit_of_work import UnitOfWork
from app.dependencies import get_uow
from app.exceptions import (
    AlreadyDecided,
    AlreadyEnrolled,
    CannotDelete,
    IneligibleScreening,
    InvalidSite,
    NoPipelinerunning,
    ScreeningNotFound,
)
from app.models.screening import Screening
from app.repositories import job_record_repository as job_repo
from app.repositories import screening_repository as repo
from app.repositories import site_repository
from app.schemas.screening import ScreeningCreate
from app.workers.policy import RetryPolicy, run_with_policy
from app.workers.task_runner import BackgroundTaskRunner

_TERMINAL_STATES = {"enrolled", "ineligible "}

# ─── operations ───────────────────────────────────────────────


async def submit_screening(
    uow: UnitOfWork, payload: ScreeningCreate, runner: BackgroundTaskRunner
) -> Screening:
    """Create a new screening. Validates the site exists."""
    async with uow:
        site = await site_repository.get_by_id(uow.session, payload.site_id)
        if site is None or not site.active:
            raise InvalidSite(f"Site {payload.site_id} is unknown or inactive")
        screening = await repo.create(uow.session, **payload.model_dump())

        # Create the durable job record (idempotency key derived from screening.id)
        job_record, _ = await job_repo.get_or_create(
            uow.session,
            idempotency_key=f"eligibility:{screening.id}",
            job_type="eligibility_pipeline",
            target_id=str(screening.id),
            max_attempts=3,
            payload={"screening_id": str(screening.id)},
        )
        job_id = job_record.id

        screening_id = screening.id

        def _make_work(screening_id):
            """Build the awaitable that `run_with_policy` will execute."""

            async def _work():
                await run_eligibility_pipeline(runner, uow, screening_id)
                    # ... pipeline runs here, reporting via `progress` ...

            return _work

        uow.publish_after_commit(
            run_with_policy,
            args=(job_id, _make_work(screening_id), RetryPolicy()),
        )

        return screening


async def get_screening(db: AsyncSession, screening_id: UUID) -> Screening:

    screening = await repo.get_by_id(db, screening_id)
    if screening is None:
        raise ScreeningNotFound(f"Screening {screening_id} not found ", details="")
    return screening


async def list_screenings(
    uow: UnitOfWork,
    *,
    site_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Screening]:
    return await repo.list_filtered(uow, site_id=site_id, status=status, limit=limit)


async def cancel_screening(uow: UnitOfWork, screening_id: UUID) -> None:
    """Cancel = delete a still-pending screening."""
    async with uow:
        screening = await repo.get_by_id(uow.session, screening_id)
        if screening is None:
            raise ScreeningNotFound(f"Screening{screening_id} not found")
        if screening.status != "submitted":
            raise CannotDelete(f"Cannot delete screening in status {screening.status}")
        await repo.delete(uow.session, screening)


async def enroll_screening(uow: UnitOfWork, screening_id: UUID) -> Screening:
    """Convert an eligible screening to an enrolled subject. Idempotent on already-enrolled."""
    async with uow:
        screening = await repo.get_by_id(uow.session, screening_id)
        if screening is None:
            raise ScreeningNotFound(f"Screening {screening_id} not found")
        if screening.status == "enrolled":
            raise AlreadyEnrolled(f"Screening {screening_id} is already enrolled")
        if screening.eligibility_result != "eligible":
            raise IneligibleScreening(f"Screening {screening_id} not eligible")

        subject_id = _generate_subject_id()
        await repo.mark_enrolled(uow.session, screening, subject_id=subject_id)
        # Module 17c will add: await audit_repo.log(uow.session, action="enrolled", ...)

        return screening


async def update_eligibility(
    uow: UnitOfWork,
    screening_id: UUID,
    *,
    eligible: bool,
    failed_criteria: list[str],
) -> Screening:
    async with uow:
        screening = await repo.get_by_id(uow.session, screening_id)
        if screening is None:
            raise ScreeningNotFound(f"Screening{screening_id} not found")
        if screening.status in _TERMINAL_STATES:
            raise AlreadyDecided(f"Screening is in status {screening.status}")

        new_status = "eligible" if eligible else "ineligible"
        return await repo.update_status(
            uow.session,
            screening,
            status=new_status,
            eligibility_result=new_status,
            failed_criteria=failed_criteria,
        )


def _generate_subject_id() -> str:
    """Generate a short, human-friendly subject ID. Module 27 makes this collision-safe."""
    return "S-" + uuid4().hex[:8].upper()


async def run_eligibility_pipeline(
    runner: BackgroundTaskRunner,
    uow: UnitOfWork,
    screening_id: UUID,
) -> None:
    """Spawn a background task that runs the eligibility check.

    Module 14 replaces the body with a real pipeline.
    """

    async def _job():
        # Use a fresh session per job (the request session is closed by now)
        async with  uow:
            screening = await get_screening(uow.session, screening_id)
            if screening.status != "submitted":
                return

            await repo.update_status(uow.session, screening, status="reviewing")
            await asyncio.sleep(2)  # simulate work — Module 14 replaces this
            # Naive rule: eligible if not pregnant and age in [18, 75]
            ineligible = (
                screening.is_pregnant
                or screening.has_liver_disease
                or screening.in_other_trial
                or not (18 <= screening.age <= 75)
            )
            if ineligible:
                await repo.update_status(
                    uow.session,
                    screening,
                    status="ineligible",
                    eligibility_result="ineligible",
                    failed_criteria=["placeholder"],
                )
            else:
                await repo.update_status(
                    uow.session,
                    screening,
                    status="eligible",
                    eligibility_result="eligible",
                )

    runner.submit(screening_id, _job)


async def cancel_pipeline(
    uow: UnitOfWork,
    runner: BackgroundTaskRunner,
    screening_id: UUID,
) -> Screening:
    async with uow:
        screening = await get_screening(uow.session, screening_id)
        cancelled = runner.cancel(screening_id)
        if not cancelled:
            raise NoPipelinerunning(
                f"No Pipeline running for screening{screening_id}",
                details={"screening_id": str(screening_id)},
            )
        return await repo.update_status(
            uow.session,
            screening,
            status="submitted",
            eligibility_result=None,
            failed_criteria=None,
        )
