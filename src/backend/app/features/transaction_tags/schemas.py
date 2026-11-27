from datetime import datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CATEGORIES = (
    "housing",
    "groceries",
    "loan_leasing",
    "insurance",
    "health",
    "transport",
    "restaurants",
    "shopping",
    "subscriptions_media",
    "leisure_travel",
    "taxes",
    "children",
    "other",
)
Severity = Literal["negligible", "minor", "moderate", "major", "critical"]
SEVERITIES = get_args(Severity)
RowSource = Literal["booking", "card_transaction"]
SetBy = Literal["rule", "model", "customer"]
SeverityScope = Literal["category", "payee", "booking"]
SeveritySource = Literal["booking", "payee", "category", "default"]
SeveritySetBy = Literal["model", "customer"]


class TransactionTag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    row_source: RowSource
    row_id: str
    category: str
    category_set_by: SetBy
    category_model: str | None
    category_confirmed: bool
    created_at: datetime
    updated_at: datetime


class Categorisation(BaseModel):
    tagged_by_rule: int
    tagged_by_model: int
    already_tagged: int
    skipped: int  # rows Apertus gave no valid category, so they stay untagged for the next call


class RatedTransactionTag(TransactionTag):
    severity: str
    severity_source: SeveritySource


class SeveritySetting(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    scope: SeverityScope
    key: str
    severity: str
    set_by: SeveritySetBy
    model: str | None
    confirmed: bool
    reason: str | None
    created_at: datetime
    updated_at: datetime


class RequestSeverityUpdate(BaseModel):
    scope: SeverityScope
    key: str = Field(min_length=1)
    severity: Severity


class ResponseSeveritySetting(BaseModel):
    id: UUID
    scope: SeverityScope
    key: str
    severity: str
    set_by: SeveritySetBy
    model: str | None
    confirmed: bool
    reason: str | None
    created_at: datetime
    updated_at: datetime


class ResponseTransactionTag(BaseModel):
    id: UUID
    row_source: RowSource
    row_id: str
    category: str
    category_set_by: SetBy
    category_model: str | None
    category_confirmed: bool
    severity: str
    severity_source: SeveritySource
    created_at: datetime
    updated_at: datetime


class ResponseCategorisation(BaseModel):
    tagged_by_rule: int
    tagged_by_model: int
    already_tagged: int
    skipped: int


class RowCategory(BaseModel):
    """What Apertus answers for one row; the category is checked against `CATEGORIES` by us."""

    ref: str
    category: str = Field(json_schema_extra={"enum": list(CATEGORIES)})


class BatchCategories(BaseModel):
    rows: list[RowCategory]


class CategorySeverity(BaseModel):
    """What Apertus answers for one category; both values are checked against our lists by us."""

    category: str = Field(json_schema_extra={"enum": list(CATEGORIES)})
    severity: str = Field(json_schema_extra={"enum": list(SEVERITIES)})
    reason: str


class CategorySeverities(BaseModel):
    categories: list[CategorySeverity]
