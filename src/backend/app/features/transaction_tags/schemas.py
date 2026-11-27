from datetime import datetime
from typing import Literal
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
RowSource = Literal["booking", "card_transaction"]
SetBy = Literal["rule", "model", "customer"]


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


class ResponseTransactionTag(BaseModel):
    id: UUID
    row_source: RowSource
    row_id: str
    category: str
    category_set_by: SetBy
    category_model: str | None
    category_confirmed: bool
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
