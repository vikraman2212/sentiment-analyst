"""FastAPI application factory and global exception handlers."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import ConflictError, ExtractionError, NotFoundError
from app.core.logging import configure_logging

configure_logging(log_level=settings.LOG_LEVEL)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.services.storage import StorageError, storage_service

    try:
        await storage_service.ensure_bucket_exists()
    except StorageError as exc:
        logger.error("startup_storage_unavailable", error=exc.detail)
    yield


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(
        title="Advisor Sentiment API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    # Allow all origins — local Wi-Fi Flutter client on same network
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)
    _register_routers(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        logger.warning("not_found", path=str(request.url), detail=exc.detail)
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        logger.warning("conflict", path=str(request.url), detail=exc.detail)
        return JSONResponse(status_code=409, content={"detail": exc.detail})

    @app.exception_handler(ExtractionError)
    async def extraction_handler(request: Request, exc: ExtractionError) -> JSONResponse:
        logger.warning("extraction_error", path=str(request.url), detail=exc.detail)
        return JSONResponse(status_code=422, content={"detail": exc.detail})


def _register_routers(app: FastAPI) -> None:
    from app.api.v1.router import router as v1_router

    app.include_router(v1_router, prefix="/api/v1")


app = create_app()
