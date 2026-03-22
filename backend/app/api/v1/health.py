"""Health and readiness endpoints.

Two endpoints:

* ``GET /health`` — liveness probe.  Returns ``200 OK`` immediately without
  touching any external dependency.  Suitable for Kubernetes liveness checks.

* ``GET /health/ready`` — readiness probe.  Performs lightweight connectivity
  checks against critical dependencies (database, MinIO, OpenSearch).
  Returns ``200 OK`` when all checks pass; ``503 Service Unavailable`` when
  any dependency is unhealthy.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.opensearch import get_opensearch_client
from app.db.session import AsyncSessionLocal
from app.services.storage import storage_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    response_description="Service is alive",
    status_code=status.HTTP_200_OK,
)
async def liveness() -> dict[str, str]:
    """Return 200 OK to indicate the process is running.

    No external dependency checks are performed here.
    """
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    response_description="Service is ready to handle requests",
)
async def readiness() -> JSONResponse:
    """Check critical external dependencies and return readiness status.

    Checks performed:

    * **database** — executes a lightweight ``SELECT 1`` query.
    * **storage** — verifies the MinIO bucket is accessible.
    * **opensearch** — pings the OpenSearch cluster.

    Returns:
        200 with ``{"status": "ready", "checks": {...}}`` when all pass.
        503 with ``{"status": "unavailable", "checks": {...}}`` when any fail.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # --- database -----------------------------------------------------------
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_database_failed", error=str(exc))
        checks["database"] = "unavailable"
        all_ok = False

    # --- storage (MinIO) ----------------------------------------------------
    try:
        await storage_service.ensure_bucket_exists()
        checks["storage"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_storage_failed", error=str(exc))
        checks["storage"] = "unavailable"
        all_ok = False

    # --- opensearch ---------------------------------------------------------
    try:
        client = get_opensearch_client()
        await client.ping()
        checks["opensearch"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_opensearch_failed", error=str(exc))
        checks["opensearch"] = "unavailable"
        all_ok = False

    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    body = {"status": "ready" if all_ok else "unavailable", "checks": checks}
    return JSONResponse(status_code=http_status, content=body)
