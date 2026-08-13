from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CompanyCreate(BaseModel):
    ticker: str
    name: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    market_cap: Decimal | None = None
    is_active: bool = True


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    name: str
    exchange: str
    sector: str | None
    industry: str | None
    market_cap: Decimal | None
    is_active: bool


class CompanyUpdate(BaseModel):
    name: str | None = None
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: Decimal | None = None
    is_active: bool | None = None
