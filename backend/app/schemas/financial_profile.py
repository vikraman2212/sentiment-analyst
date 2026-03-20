import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FinancialProfileCreate(BaseModel):
    client_id: uuid.UUID
    total_aum: Decimal | None = None
    ytd_return_pct: Decimal | None = None
    risk_profile: str | None = None


class FinancialProfileUpdate(BaseModel):
    total_aum: Decimal | None = None
    ytd_return_pct: Decimal | None = None
    risk_profile: str | None = None


class FinancialProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    total_aum: Decimal | None
    ytd_return_pct: Decimal | None
    risk_profile: str | None
