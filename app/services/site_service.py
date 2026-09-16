from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import SiteNotFound
from app.models.site import Site
from app.repositories import site_repository


async def get_all_sites(db: AsyncSession, *, active: bool | None = None) -> list[Site]:
    return await site_repository.list_all(db, active=active)


async def get_by_site_id(db: AsyncSession, site_id: str) -> Site | None:
    site = await site_repository.get_by_id(db, site_id)
    if site is None:
        raise SiteNotFound(f"Site {site_id} not found")
    return site
