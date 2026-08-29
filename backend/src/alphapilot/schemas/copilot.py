from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CopilotQuestionSchema(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class CopilotFactReferenceSchema(BaseModel):
    fact_id: str
    source: str
    field: str
    label: str
    value: Any


class CopilotAnswerSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    answer: str
    scope: str
    portfolio_id: UUID
    position_id: UUID | None
    ticker: str | None
    as_of_date: date | None
    grounding_status: str
    fact_refs: tuple[CopilotFactReferenceSchema, ...]
    limitations: tuple[str, ...]
    provider: str
    model: str


class CopilotStatusSchema(BaseModel):
    enabled: bool
    provider: str
    model: str | None
    available: bool
    status: str
