"""API contract tests for the clients router.

Covers: list (with and without advisor filter), create, get by id, patch, delete.
All service calls are mocked; no database required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from tests.api.v1.conftest import async_client, make_app_with_router

_ADVISOR_ID = uuid.uuid4()
_CLIENT_ID = uuid.uuid4()


def _mock_client() -> MagicMock:
    m = MagicMock()
    m.id = _CLIENT_ID
    m.advisor_id = _ADVISOR_ID
    m.first_name = "John"
    m.last_name = "Doe"
    m.next_review_date = None
    return m


def _make_app():
    from app.api.v1.clients import router
    return make_app_with_router(router)


# ---------------------------------------------------------------------------
# GET /clients/
# ---------------------------------------------------------------------------


async def test_list_clients_returns_200() -> None:
    """GET /clients/ returns 200 with a list of clients."""
    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.list = AsyncMock(return_value=[_mock_client()])
        async with async_client(app) as client:
            response = await client.get("/clients/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    body = response.json()[0]
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"


async def test_list_clients_filtered_by_advisor() -> None:
    """GET /clients/?advisor_id=... passes the filter through to the service."""
    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc = mock_svc_cls.return_value
        mock_svc.list = AsyncMock(return_value=[_mock_client()])
        async with async_client(app) as client:
            response = await client.get(f"/clients/?advisor_id={_ADVISOR_ID}")

    assert response.status_code == 200
    mock_svc.list.assert_awaited_once_with(_ADVISOR_ID)


# ---------------------------------------------------------------------------
# POST /clients/
# ---------------------------------------------------------------------------


async def test_create_client_returns_201() -> None:
    """POST /clients/ returns 201 with the created client payload."""
    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.create = AsyncMock(return_value=_mock_client())
        async with async_client(app) as client:
            response = await client.post(
                "/clients/",
                json={
                    "first_name": "John",
                    "last_name": "Doe",
                    "advisor_id": str(_ADVISOR_ID),
                },
            )

    assert response.status_code == 201
    assert response.json()["first_name"] == "John"


async def test_create_client_conflict_returns_409() -> None:
    """POST /clients/ returns 409 when a duplicate client exists."""
    from app.core.exceptions import ConflictError

    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.create = AsyncMock(
            side_effect=ConflictError("Client already exists")
        )
        async with async_client(app) as client:
            response = await client.post(
                "/clients/",
                json={
                    "first_name": "John",
                    "last_name": "Doe",
                    "advisor_id": str(_ADVISOR_ID),
                },
            )

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /clients/{client_id}
# ---------------------------------------------------------------------------


async def test_get_client_returns_200() -> None:
    """GET /clients/{id} returns 200 with full client payload."""
    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.get = AsyncMock(return_value=_mock_client())
        async with async_client(app) as client:
            response = await client.get(f"/clients/{_CLIENT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(_CLIENT_ID)
    assert response.json()["advisor_id"] == str(_ADVISOR_ID)


async def test_get_client_not_found_returns_404() -> None:
    """GET /clients/{id} returns 404 for an unknown client."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.get = AsyncMock(
            side_effect=NotFoundError("Client not found")
        )
        async with async_client(app) as client:
            response = await client.get(f"/clients/{uuid.uuid4()}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /clients/{client_id}
# ---------------------------------------------------------------------------


async def test_patch_client_returns_200() -> None:
    """PATCH /clients/{id} returns 200 with updated fields."""
    updated = _mock_client()
    updated.first_name = "Jonathan"

    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.update = AsyncMock(return_value=updated)
        async with async_client(app) as client:
            response = await client.patch(
                f"/clients/{_CLIENT_ID}", json={"first_name": "Jonathan"}
            )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Jonathan"


# ---------------------------------------------------------------------------
# DELETE /clients/{client_id}
# ---------------------------------------------------------------------------


async def test_delete_client_returns_204() -> None:
    """DELETE /clients/{id} returns 204 No Content."""
    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.delete = AsyncMock(return_value=None)
        async with async_client(app) as client:
            response = await client.delete(f"/clients/{_CLIENT_ID}")

    assert response.status_code == 204


async def test_delete_client_not_found_returns_404() -> None:
    """DELETE /clients/{id} returns 404 for an unknown client."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.clients.ClientService") as mock_svc_cls:
        mock_svc_cls.return_value.delete = AsyncMock(
            side_effect=NotFoundError("Client not found")
        )
        async with async_client(app) as client:
            response = await client.delete(f"/clients/{uuid.uuid4()}")

    assert response.status_code == 404
