"""Site routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.schemas.site import SiteResponse
from app.services import site_service as service

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=list[SiteResponse])
async def list_sites(
    active: bool | None = None, db: AsyncSession = Depends(get_db_session)
):
    return await service.get_all_sites(db, active=active)


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(site_id: str, db: AsyncSession = Depends(get_db_session)):
    return await service.get_by_site_id(db, site_id)
