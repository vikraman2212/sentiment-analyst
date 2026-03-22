"""API contract tests for the advisors router.

Two flavours of test per endpoint:
  - Happy path: service returns expected data → correct status + shape.
  - Error case: service raises domain exception → correct HTTP status code.

All service calls are mocked at the class boundary; no database is needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.api.v1.conftest import async_client, make_app_with_router

_ADVISOR_ID = uuid.uuid4()

_ADVISOR_DICT = {
    "id": str(_ADVISOR_ID),
    "full_name": "Alice Advisor",
    "email": "alice@example.com",
    "default_tone": "professional",
}


def _mock_advisor() -> MagicMock:
    m = MagicMock()
    m.id = _ADVISOR_ID
    m.full_name = "Alice Advisor"
    m.email = "alice@example.com"
    m.default_tone = "professional"
    return m


def _make_app():
    from app.api.v1.advisors import router
    return make_app_with_router(router)


# ---------------------------------------------------------------------------
# POST /advisors/
# ---------------------------------------------------------------------------


async def test_create_advisor_returns_201() -> None:
    """POST /advisors/ returns 201 and the advisor payload."""
    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.create = AsyncMock(return_value=_mock_advisor())
        async with async_client(app) as client:
            response = await client.post(
                "/advisors/",
                json={"full_name": "Alice Advisor", "email": "alice@example.com"},
            )

    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Alice Advisor"
    assert body["email"] == "alice@example.com"


async def test_create_advisor_conflict_returns_409() -> None:
    """POST /advisors/ returns 409 when ConflictError is raised."""
    from app.core.exceptions import ConflictError

    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.create = AsyncMock(
            side_effect=ConflictError("Advisor already exists")
        )
        async with async_client(app) as client:
            response = await client.post(
                "/advisors/",
                json={"full_name": "Alice Advisor", "email": "alice@example.com"},
            )

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /advisors/
# ---------------------------------------------------------------------------


async def test_list_advisors_returns_200_with_list() -> None:
    """GET /advisors/ returns 200 and a list."""
    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.list_all = AsyncMock(return_value=[_mock_advisor()])
        async with async_client(app) as client:
            response = await client.get("/advisors/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["full_name"] == "Alice Advisor"


async def test_list_advisors_returns_empty_list() -> None:
    """GET /advisors/ returns 200 with an empty list when none exist."""
    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.list_all = AsyncMock(return_value=[])
        async with async_client(app) as client:
            response = await client.get("/advisors/")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /advisors/{advisor_id}
# ---------------------------------------------------------------------------


async def test_get_advisor_returns_200() -> None:
    """GET /advisors/{id} returns 200 with full advisor payload."""
    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.get = AsyncMock(return_value=_mock_advisor())
        async with async_client(app) as client:
            response = await client.get(f"/advisors/{_ADVISOR_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(_ADVISOR_ID)


async def test_get_advisor_not_found_returns_404() -> None:
    """GET /advisors/{id} returns 404 when the advisor does not exist."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.get = AsyncMock(
            side_effect=NotFoundError("Advisor not found")
        )
        async with async_client(app) as client:
            response = await client.get(f"/advisors/{uuid.uuid4()}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /advisors/{advisor_id}
# ---------------------------------------------------------------------------


async def test_patch_advisor_returns_200() -> None:
    """PATCH /advisors/{id} returns 200 with updated payload."""
    updated = _mock_advisor()
    updated.default_tone = "casual"

    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.update = AsyncMock(return_value=updated)
        async with async_client(app) as client:
            response = await client.patch(
                f"/advisors/{_ADVISOR_ID}", json={"default_tone": "casual"}
            )

    assert response.status_code == 200
    assert response.json()["default_tone"] == "casual"


# ---------------------------------------------------------------------------
# DELETE /advisors/{advisor_id}
# ---------------------------------------------------------------------------


async def test_delete_advisor_returns_204() -> None:
    """DELETE /advisors/{id} returns 204 No Content."""
    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.delete = AsyncMock(return_value=None)
        async with async_client(app) as client:
            response = await client.delete(f"/advisors/{_ADVISOR_ID}")

    assert response.status_code == 204


async def test_delete_advisor_not_found_returns_404() -> None:
    """DELETE /advisors/{id} returns 404 when the advisor does not exist."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.advisors.AdvisorService") as mock_svc_cls:
        mock_svc_cls.return_value.delete = AsyncMock(
            side_effect=NotFoundError("Advisor not found")
        )
        async with async_client(app) as client:
            response = await client.delete(f"/advisors/{uuid.uuid4()}")

    assert response.status_code == 404
