from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.prompts import load_prompts
from app.features.transaction_tags.schemas import Category

PROMPTS = load_prompts(prompts_py=__file__)
AMOUNT_MAX = Decimal(100_000)
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Budget(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    category: Category
    amount_chf: Decimal
    created_at: datetime


class RequestBudgetCreate(BaseModel):
    category: Category
    amount_chf: Decimal = Field(gt=0, le=AMOUNT_MAX, decimal_places=2)


class RequestBudgetUpdate(BaseModel):
    amount_chf: Decimal = Field(gt=0, le=AMOUNT_MAX, decimal_places=2)


class ResponseBudget(BaseModel):
    id: UUID
    category: Category
    amount_chf: float
    created_at: datetime


class CompareBudgetsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = Field(default=None, pattern=MONTH_PATTERN, description=PROMPTS["month"])


class BudgetLine(BaseModel):
    category: Category
    budget_chf: Decimal
    spent_chf: Decimal
    # Negative when over.
    left_chf: Decimal
    over: bool


class UnbudgetedSpending(BaseModel):
    category: str
    spent_chf: Decimal


class BudgetSummary(BaseModel):
    month: str
    days_in_month: int
    # The day of the month today; None for a month that has ended, 0 for one still to come.
    days_elapsed: int | None
    # Totals of the budgeted categories.
    budget_chf: Decimal
    spent_chf: Decimal
    left_chf: Decimal
    over: bool
    budgets: list[BudgetLine]
    unbudgeted: list[UnbudgetedSpending]
    # Last, so a cut in the tool result drops ids before any figure.
    row_ids: dict[str, list[str]]


class ResponseBudgetSummary(BudgetSummary):
    pass
