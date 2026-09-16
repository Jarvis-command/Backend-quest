import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session, close_db
from app.dependencies import get_db_session
from app.exceptions import DomainError
from app.models.site import Site
from app.repositories import site_repository
from app.routers import restaurant, screenings, sites
from app.workers.task_runner import BackgroundTaskRunner

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_SITES = [
    Site(id="SITE-001", name="Mass General", active=True),
    Site(id="SITE-002", name="Stanford Health", active=True),
    Site(id="SITE-003", name="Old Site", active=False),
]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        logger.info(
            "DomainError on %s %s: %s (code=%s)",
            request.method,
            request.url.path,
            exc.message,
            exc.code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "internal_error", "message": "Internal server error"}
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Run pending migrations via isolated OS process
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Alembic failed: %s", result.stderr)
        raise RuntimeError("Migration failed")
    logger.info("Migrations up to date")

    # 2. Seed initial default sites on startup
    async with async_session() as db:
        inserted = await site_repository.seed(db, DEFAULT_SITES)
        if inserted:
            logger.info("Seeded %d sites", inserted)

    # 3. Server runs and handles requests
    app.state.executor = ThreadPoolExecutor(max_workers=4)
    app.state.task_runner = BackgroundTaskRunner(executor=app.state.executor)
    logger.info("Worker ready")
    yield

    # 4. Cleanup: Dispose of connection pool on shutdown
    await app.state.task_runner.shutdown()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(sites.router, prefix=settings.api_prefix)
    app.include_router(screenings.router, prefix=settings.api_prefix)
    app.include_router(restaurant.router)

    @app.get("/")
    def root():
        return {
        "service": "Menu Service",
        "status": "ok"
        }   

    @app.get("/")
    def root():
        return {"service": settings.app_name, "version": settings.app_version}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/db")
    async def health_db(db: AsyncSession = Depends(get_db_session)):
        try:
            await db.execute(text("SELECT 1"))
            return {"db": "ok"}
        except SQLAlchemyError:
            raise HTTPException(503, detail={"db": "Unreachable"})

    return app


app = create_app()
