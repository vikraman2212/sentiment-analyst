import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.schemas.advisor import AdvisorCreate, AdvisorResponse, AdvisorUpdate
from app.schemas.client import ClientResponse
from app.services.advisor_service import AdvisorService
from app.services.client_service import ClientService

router = APIRouter(prefix="/advisors", tags=["advisors"])


@router.post("/", response_model=AdvisorResponse, status_code=status.HTTP_201_CREATED)
async def create_advisor(
    payload: AdvisorCreate,
    db: AsyncSession = Depends(get_db),
) -> AdvisorResponse:
    return await AdvisorService(db).create(payload)


@router.get("/", response_model=list[AdvisorResponse])
async def list_advisors(
    db: AsyncSession = Depends(get_db),
) -> list[AdvisorResponse]:
    return await AdvisorService(db).list_all()


@router.get("/{advisor_id}", response_model=AdvisorResponse)
async def get_advisor(
    advisor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AdvisorResponse:
    return await AdvisorService(db).get(advisor_id)


@router.patch("/{advisor_id}", response_model=AdvisorResponse)
async def update_advisor(
    advisor_id: uuid.UUID,
    payload: AdvisorUpdate,
    db: AsyncSession = Depends(get_db),
) -> AdvisorResponse:
    return await AdvisorService(db).update(advisor_id, payload)


@router.delete("/{advisor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_advisor(
    advisor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await AdvisorService(db).delete(advisor_id)


@router.get("/{advisor_id}/clients", response_model=list[ClientResponse])
async def list_advisor_clients(
    advisor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ClientResponse]:
    return await ClientService(db).list_by_advisor(advisor_id)
