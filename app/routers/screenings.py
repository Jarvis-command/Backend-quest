import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.unit_of_work import UnitOfWork
from app.dependencies import (
    Pagination,
    get_db_session,
    get_pagination,
    get_task_runner,
    get_uow,
)
from app.schemas.screening import EligibilityUpdate, ScreeningCreate, ScreeningResponse
from app.services import screening_service as service
from app.services.screening_service import run_eligibility_pipeline

router = APIRouter(prefix="/screenings", tags=["screenings"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ScreeningResponse, status_code=201)
async def create_screening(
    payload: ScreeningCreate,
    uow: UnitOfWork = Depends(get_uow),
    runner = Depends (get_task_runner),
):
    screening = await service.submit_screening(uow,payload,runner)
    
    return screening
        # logger.info("create_screening: meta=%s", meta)
        # return await service.submit_screening(db, payload)


@router.get("", response_model=list[ScreeningResponse])
async def list_screenings(
    site_id: str | None = None,
    status: str | None = None,
    # `default_list_limit` came from Module 04's exercise. Hardcode `50` if you skipped it.
    pagination: Pagination = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
):
    return await service.list_screenings(
        db,
        site_id=site_id,
        status=status,
        limit=pagination.limit,
        # offset will be wired in when the repo supports it (Module 27)
    )


@router.get("/{screening_id}", response_model=ScreeningResponse)
async def get_screening(screening_id: UUID, db: AsyncSession = Depends(get_db_session)):
    return await service.get_screening(db, screening_id)


@router.post("/{screening_id}/enroll", response_model=ScreeningResponse)
async def enroll(screening_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    return await service.enroll_screening(uow, screening_id)


@router.post("/{screening_id}/_set_eligibility", response_model=ScreeningResponse)
async def set_eligibility(
    screening_id: UUID,
    payload: EligibilityUpdate,
    uow: UnitOfWork = Depends(get_uow),
):
    return await service.update_eligibility(
        uow,
        screening_id,
        eligible=payload.eligible,
        failed_criteria=payload.failed_criteria,
    )


@router.delete("/{screening_id}", status_code=204)
async def delete_screening(screening_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    return await service.cancel_screening(uow, screening_id)

@router.post("/{screening_id}/cancel-pipeline", response_model= ScreeningResponse)
async def cancel_pipeline_route(
    screening_id:UUID,
    uow: UnitOfWork = Depends(get_uow),
    runner = Depends (get_task_runner),
):
    return await service.cancel_pipeline(uow, runner, screening_id)

