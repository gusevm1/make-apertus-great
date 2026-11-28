from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model, field_validator

from app.core.prompts import load_prompts
from app.features.ledger.schemas import Kind

PROMPTS = load_prompts(prompts_py=__file__)

Certainty = Literal["low", "medium", "high"]
CERTAINTIES = get_args(Certainty)
Severity = Literal["negligible", "minor", "moderate", "major", "critical"]
SEVERITIES = get_args(Severity)
RowSource = Literal["booking", "card_transaction"]
CorrectionScope = Literal["payee", "booking"]
CertaintyFilter = Literal["low", "medium", "high", "unknown"]
Category = Literal[
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
]
CATEGORIES = get_args(Category)
SetBy = Literal["rule", "model", "customer"]
SeverityScope = Literal["category", "payee", "booking"]
SeveritySource = Literal["booking", "payee", "category", "default"]
SeveritySetBy = Literal["model", "customer"]
RunStatus = Literal["queued", "running", "done", "failed"]
PersonalTagSetBy = Literal["model", "customer"]
CategorisationScope = Literal["untagged", "unconfirmed"]
MAX_INFERRED_TAGS = 10
CATEGORY_NAME_MAX_LENGTH = 40
CATEGORY_DESCRIPTION_MAX_LENGTH = 200
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
    category_alternative: str | None
    created_at: datetime
    updated_at: datetime


class CustomCategory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    description: str
    created_at: datetime


def category_names(custom: list[CustomCategory]) -> list[str]:
    """The built-in categories, then the customer's own."""
    return [*CATEGORIES, *(category.name for category in custom)]


class SpendingCategory(BaseModel):
    """A category a row can get: a built-in one or one the customer added."""

    name: str
    description: str
    custom: bool


class RequestSpendingCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=CATEGORY_NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=CATEGORY_DESCRIPTION_MAX_LENGTH)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ResponseSpendingCategory(BaseModel):
    name: str
    description: str
    custom: bool


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


class CategorisationRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    status: RunStatus
    tagged_by_rule: int
    tagged_by_correction: int
    tagged_by_model: int
    already_tagged: int
    skipped: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RatedTransactionTag(TransactionTag):
    severity: str
    severity_source: SeveritySource
    date: date
    text: str
    payee: str
    amount_chf: Decimal
    payee_usual_category: str  # the most common category of the payee's rows


class RequestCategoryCorrectionCreate(BaseModel):
    scope: CorrectionScope
    key: str = Field(min_length=1, max_length=200)  # a payee, or `<row_source>:<row_id>`
    # A built-in category or one of the customer's own, checked by the service.
    category: str = Field(min_length=1, max_length=CATEGORY_NAME_MAX_LENGTH)


class CategoryCorrectionResult(BaseModel):
    scope: CorrectionScope
    key: str
    category: str
    rows_changed: int


class ResponseCategoryCorrection(BaseModel):
    scope: CorrectionScope
    key: str
    category: str
    rows_changed: int


class CategorySummary(BaseModel):
    category: str | None  # None: spending rows not categorised yet
    total_chf: Decimal
    row_count: int
    high: int
    medium: int
    low: int
    unknown: int
    confirmed: int


class ResponseCategorySummary(BaseModel):
    category: str | None
    total_chf: Decimal
    row_count: int
    high: int
    medium: int
    low: int
    unknown: int
    confirmed: int


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
    category_alternative: str | None
    severity: str
    severity_source: SeveritySource
    date: date
    text: str
    payee: str
    amount_chf: Decimal
    payee_usual_category: str
    created_at: datetime
    updated_at: datetime


class RequestCategorisationCreate(BaseModel):
    # unconfirmed: also judge again what Apertus decided and the customer has not confirmed.
    scope: CategorisationScope = "untagged"


class ResponseCategorisationRun(BaseModel):
    id: UUID
    status: RunStatus
    tagged_by_rule: int
    tagged_by_correction: int
    tagged_by_model: int
    already_tagged: int
    skipped: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RowCategory(BaseModel):
    """What Apertus answers for one row; the category is checked against `CATEGORIES` by us."""

    ref: str
    # Written before the category, so each answer is tied to its row and none slips onto the next.
    payee: str | None = Field(default=None, description=PROMPTS["categorise_payee_field"])
    category: str = Field(json_schema_extra={"enum": list(CATEGORIES)})
    certainty: str | None = Field(default=None, json_schema_extra={"enum": list(CERTAINTIES)})
    alternative: str | None = Field(
        default=None,
        description=PROMPTS["categorise_alternative_field"],
        json_schema_extra={"enum": list(CATEGORIES)},
    )


class BatchCategories(BaseModel):
    rows: list[RowCategory]


def batch_categories_schema(categories: list[str]) -> type[BatchCategories]:
    """`BatchCategories` whose category enums hold these categories, the customer's own too."""
    enum: list[JsonValue] = list(categories)
    row = create_model(
        "RowCategory",
        __base__=RowCategory,
        category=(str, Field(json_schema_extra={"enum": enum})),
        alternative=(
            str | None,
            Field(
                default=None,
                description=PROMPTS["categorise_alternative_field"],
                json_schema_extra={"enum": enum},
            ),
        ),
    )
    fields: dict[str, Any] = {"rows": (list[row], ...)}
    return create_model("BatchCategories", __base__=BatchCategories, **fields)


class CategorySeverity(BaseModel):
    """What Apertus answers for one category; both values are checked against our lists by us."""

    category: str = Field(json_schema_extra={"enum": list(CATEGORIES)})
    severity: str = Field(json_schema_extra={"enum": list(SEVERITIES)})
    reason: str


class CategorySeverities(BaseModel):
    categories: list[CategorySeverity]


def category_severities_schema(categories: list[str]) -> type[CategorySeverities]:
    """`CategorySeverities` whose category enum holds these categories, the customer's own too."""
    enum: list[JsonValue] = list(categories)
    item = create_model(
        "CategorySeverity",
        __base__=CategorySeverity,
        category=(str, Field(json_schema_extra={"enum": enum})),
    )
    fields: dict[str, Any] = {"categories": (list[item], ...)}
    return create_model("CategorySeverities", __base__=CategorySeverities, **fields)


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


SpendingGroupBy = Literal["category", "personal_tag", "severity"]
AnswerLanguage = Literal["de", "en", "fr", "it"]
# The group of spending rows that have no category yet, or no personal tag.
NOT_CATEGORISED = "not_categorised"
NO_PERSONAL_TAG = "no_personal_tag"


class SumSpendingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_by: SpendingGroupBy = Field(description=PROMPTS["group_by"])
    date_from: date | None = Field(default=None, description=PROMPTS["date_from"])
    date_to: date | None = Field(default=None, description=PROMPTS["date_to"])
    category: Category | None = Field(default=None, description=PROMPTS["category"])
    personal_tag: str | None = Field(
        default=None,
        min_length=1,
        max_length=TAG_NAME_MAX_LENGTH,
        description=PROMPTS["personal_tag"],
    )
    severity: Severity | None = Field(default=None, description=PROMPTS["severity"])
    language: AnswerLanguage = Field(default="de", description=PROMPTS["language"])


class SpendingGroup(BaseModel):
    group: str
    spent_chf: Decimal
    count: int
    # Model categories with low or no certainty that the customer has not confirmed.
    uncertain_count: int
    # Only per personal tag: money moved to own accounts for it, not counted as spent.
    saved_chf: Decimal | None


class SpendingSums(BaseModel):
    group_by: SpendingGroupBy
    spent_chf: Decimal
    count: int
    uncertain_count: int
    groups: list[SpendingGroup]
    language: AnswerLanguage
    # What to try next when the filter found nothing.
    note: str | None = None
    # Last, so a cut in the tool result drops ids before any figure.
    row_ids: dict[str, list[str]]
