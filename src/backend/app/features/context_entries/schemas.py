from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["goal", "fact", "preference"]
Status = Literal["proposed", "active", "dismissed", "replaced"]
Source = Literal["customer", "chat"]
TEXT_MAX_LENGTH = 300
ACTIVE_ENTRIES_MAX = 50
AMOUNT_MAX = Decimal("9999999999.99")


class ContextEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    kind: Kind
    status: Status
    text: str
    amount_chf: Decimal | None
    target_date: date | None
    source: Source
    source_id: UUID | None
    replaced_by_id: UUID | None
    replaces_id: UUID | None
    created_at: datetime


class RequestContextEntryCreate(BaseModel):
    kind: Kind
    text: str = Field(min_length=1, max_length=TEXT_MAX_LENGTH)
    amount_chf: Decimal | None = Field(default=None, ge=0, le=AMOUNT_MAX, decimal_places=2)
    target_date: date | None = None


class RequestContextEntryUpdate(BaseModel):
    kind: Kind | None = None
    text: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX_LENGTH)
    amount_chf: Decimal | None = Field(default=None, ge=0, le=AMOUNT_MAX, decimal_places=2)
    target_date: date | None = None

    @field_validator("kind", "text")
    @classmethod
    def _not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Leave the field out to keep it, it cannot be null")
        return value


class ResponseContextEntry(BaseModel):
    id: UUID
    kind: Kind
    status: Status
    text: str
    amount_chf: float | None
    target_date: date | None
    source: Source
    source_id: UUID | None
    replaced_by_id: UUID | None
    replaces_id: UUID | None
    created_at: datetime
