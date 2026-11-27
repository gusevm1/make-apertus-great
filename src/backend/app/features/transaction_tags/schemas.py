from datetime import date, datetime
from decimal import Decimal
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.ledger.schemas import Kind

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
Certainty = Literal["low", "medium", "high"]
CERTAINTIES = get_args(Certainty)
Severity = Literal["negligible", "minor", "moderate", "major", "critical"]
SEVERITIES = get_args(Severity)
RowSource = Literal["booking", "card_transaction"]
SetBy = Literal["rule", "model", "customer"]
SeverityScope = Literal["category", "payee", "booking"]
SeveritySource = Literal["booking", "payee", "category", "default"]
SeveritySetBy = Literal["model", "customer"]
PersonalTagSetBy = Literal["model", "customer"]
MAX_INFERRED_TAGS = 10
TAG_NAME_MAX_LENGTH = 40
TAG_DESCRIPTION_MAX_LENGTH = 200


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
    category_certainty: Certainty | None
    created_at: datetime
    updated_at: datetime


class CategoryCorrection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    payee: str
    category: str
    created_at: datetime
    updated_at: datetime


class Categorisation(BaseModel):
    tagged_by_rule: int
    tagged_by_correction: int  # from the customer's correction of the payee
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
    category_certainty: Certainty | None
    severity: str
    severity_source: SeveritySource
    created_at: datetime
    updated_at: datetime


class ResponseCategorisation(BaseModel):
    tagged_by_rule: int
    tagged_by_correction: int
    tagged_by_model: int
    already_tagged: int
    skipped: int


class RowCategory(BaseModel):
    """What Apertus answers for one row; the category is checked against `CATEGORIES` by us."""

    ref: str
    category: str = Field(json_schema_extra={"enum": list(CATEGORIES)})
    certainty: str | None = Field(default=None, json_schema_extra={"enum": list(CERTAINTIES)})


class BatchCategories(BaseModel):
    rows: list[RowCategory]


class CategorySeverity(BaseModel):
    """What Apertus answers for one category; both values are checked against our lists by us."""

    category: str = Field(json_schema_extra={"enum": list(CATEGORIES)})
    severity: str = Field(json_schema_extra={"enum": list(SEVERITIES)})
    reason: str


class CategorySeverities(BaseModel):
    categories: list[CategorySeverity]


class PersonalTag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    description: str
    set_by: PersonalTagSetBy
    model: str | None
    confirmed: bool
    created_at: datetime
    updated_at: datetime


class PersonalTagAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tag_id: UUID
    owner_id: UUID
    row_source: RowSource
    row_id: str
    set_by: PersonalTagSetBy
    model: str | None
    confirmed: bool
    created_at: datetime


class PersonalTagEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    row_source: RowSource
    row_id: str
    created_at: datetime


class PersonalTagSummary(PersonalTag):
    """A tag with what its rows add up to; own transfers count their outgoing side only."""

    spending_count: int
    spending_total_chf: Decimal
    own_transfer_count: int
    own_transfer_total_chf: Decimal


class AssignedRow(PersonalTagAssignment):
    kind: Kind
    date: date
    text: str
    amount_chf: Decimal


class RequestPersonalTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=TAG_NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=TAG_DESCRIPTION_MAX_LENGTH)


class RequestPersonalTagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=TAG_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=TAG_DESCRIPTION_MAX_LENGTH)

    @field_validator("name", "description", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Cannot be null")
        return value


class RequestPersonalTagAssignmentCreate(BaseModel):
    row_source: RowSource
    row_id: str = Field(min_length=1)


class ResponsePersonalTag(BaseModel):
    id: UUID
    name: str
    description: str
    set_by: PersonalTagSetBy
    model: str | None
    confirmed: bool
    spending_count: int
    spending_total_chf: Decimal
    own_transfer_count: int
    own_transfer_total_chf: Decimal
    created_at: datetime
    updated_at: datetime


class ResponsePersonalTagAssignment(BaseModel):
    id: UUID
    row_source: RowSource
    row_id: str
    kind: Kind
    date: date
    text: str
    amount_chf: Decimal
    set_by: PersonalTagSetBy
    model: str | None
    confirmed: bool
    created_at: datetime


class InferredTag(BaseModel):
    """What Apertus proposes as a tag; we cut it to length and drop duplicates."""

    name: str
    description: str | None = None


class InferredTags(BaseModel):
    tags: list[InferredTag]


class RowPersonalTags(BaseModel):
    """What Apertus answers for one row: the names of its tags, none if no tag fits."""

    ref: str
    tags: list[str] | None = None


class BatchPersonalTags(BaseModel):
    rows: list[RowPersonalTags]
