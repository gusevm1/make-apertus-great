from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AlertKind = Literal["invoice"]
# A check with no stored setting is on or off by this.
DEFAULT_ENABLED: dict[AlertKind, bool] = {"invoice": True}
KEY_MAX_LENGTH = 200
# A booking or pending payment this close to the amount due pays the bill.
AMOUNT_TOLERANCE_CHF = Decimal("0.05")
# Without a document date, bookings from this long before the upload count as paying it.
UNDATED_LOOKBACK_DAYS = 90
PENDING_PAYMENTS_LIMIT = 1000


class Alert(BaseModel):
    key: str
    kind: AlertKind
    document_id: UUID
    document_name: str
    document_kind: Literal["invoice", "reminder"]
    payee: str | None
    amount_chf: Decimal
    due_date: date | None
    document_date: date | None


class ResponseAlert(BaseModel):
    key: str
    kind: AlertKind
    document_id: UUID
    document_name: str
    document_kind: Literal["invoice", "reminder"]
    payee: str | None
    amount_chf: Decimal
    due_date: date | None
    document_date: date | None


class AlertDismissal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    key: str
    created_at: datetime


class RequestAlertDismissalCreate(BaseModel):
    key: str = Field(min_length=1, max_length=KEY_MAX_LENGTH)


class ResponseAlertDismissal(BaseModel):
    id: UUID
    key: str
    created_at: datetime


class AlertSetting(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: AlertKind
    enabled: bool


class RequestAlertSettingUpdate(BaseModel):
    enabled: bool


class ResponseAlertSetting(BaseModel):
    kind: AlertKind
    enabled: bool
