import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.schemas.client import ClientCreate, ClientListItem, ClientResponse, ClientUpdate
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=list[ClientListItem])
async def list_clients(
    advisor_id: uuid.UUID | None = Query(None, description="Filter by advisor"),
    db: AsyncSession = Depends(get_db),
) -> list[ClientListItem]:
    return await ClientService(db).list(advisor_id)


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await ClientService(db).create(payload)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await ClientService(db).get(client_id)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    return await ClientService(db).update(client_id, payload)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await ClientService(db).delete(client_id)
