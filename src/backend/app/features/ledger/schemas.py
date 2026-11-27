import datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)
ROWS_DEFAULT = 10
ROWS_MAX = 20
# Fewer points than this make a line that says nothing.
MIN_TREND_MONTHS = 3
MAX_TREND_MONTHS = 24
TREND_MONTHS_DEFAULT = 12
MAX_PROJECTED_MONTHS = 6
PROJECTED_MONTHS_DEFAULT = 3
TOP_COUNTERPARTIES = 15

# own_transfer moves money between own accounts or into the depot; card_settlement is the card bill.
Kind = Literal["spending", "credit", "own_transfer", "card_settlement"]


class LedgerRow(BaseModel):
    source: Literal["booking", "card_transaction"]
    id: str
    account_id: str
    card_id: str | None = None
    date: datetime.date
    amount_chf: Decimal  # negative is money out, for card purchases too
    text: str
    counterparty: str | None = None
    transaction_type: str | None = None
    original_amount: Decimal | None = None
    original_currency: str | None = None
    statement_id: str | None = None
    loan_id: str | None = None
    loan_charge: Literal["interest", "amortisation"] | None = None
    kind: Kind
    # A purchase on a credit card statement that is still open; its bill can change.
    provisional: bool = False


class Selection(BaseModel):
    # An argument the tool does not have is an error the model can correct, not a dropped filter.
    model_config = ConfigDict(extra="forbid")

    text: list[str] | None = Field(default=None, min_length=1, description=PROMPTS["text"])
    kind: list[Kind] | None = Field(default=None, description=PROMPTS["kind"])
    account_id: str | None = Field(default=None, description=PROMPTS["account_id"])
    card_id: str | None = Field(default=None, description=PROMPTS["card_id"])
    amount_min: Decimal | None = Field(default=None, ge=0, description=PROMPTS["amount_min"])
    amount_max: Decimal | None = Field(default=None, ge=0, description=PROMPTS["amount_max"])

    @field_validator("text", "kind", mode="before")
    @classmethod
    def _one_value_is_a_list(cls, value: Any) -> Any:
        # The model sends one value as a string, several often as "Migros|Coop".
        values = value.split("|") if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        # An empty word would match every movement and turn a filter into "everything".
        return [item.strip() for item in values if not isinstance(item, str) or item.strip()]


class Filters(Selection):
    date_from: datetime.date | None = Field(default=None, description=PROMPTS["date_from"])
    date_to: datetime.date | None = Field(default=None, description=PROMPTS["date_to"])

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        # A period that ends before it starts matches no rows, which reads as "none".
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from is after date_to. The period starts on date_from.")
        return self


class SearchMovementsArgs(Filters):
    sort: Literal["newest", "oldest", "largest"] = Field(
        default="newest", description=PROMPTS["sort"]
    )
    limit: int = Field(default=ROWS_DEFAULT, ge=1, le=ROWS_MAX, description=PROMPTS["limit"])


class SumByCounterpartyArgs(Filters):
    limit: int = Field(
        default=TOP_COUNTERPARTIES,
        ge=1,
        le=TOP_COUNTERPARTIES,
        description=PROMPTS["counterparty_limit"],
    )


class ForecastMonthsArgs(Selection):
    months_back: int = Field(
        default=TREND_MONTHS_DEFAULT,
        ge=MIN_TREND_MONTHS,
        le=MAX_TREND_MONTHS,
        description=PROMPTS["months_back"],
    )
    months_ahead: int = Field(
        default=PROJECTED_MONTHS_DEFAULT,
        ge=1,
        le=MAX_PROJECTED_MONTHS,
        description=PROMPTS["months_ahead"],
    )


GroupBy = Literal["quarter", "year", "weekday", "account", "kind"]


class SumByGroupArgs(Filters):
    group_by: GroupBy = Field(description=PROMPTS["group_by"])


class Movement(BaseModel):
    id: str
    date: datetime.date
    amount_chf: Decimal
    text: str
    counterparty: str | None
    kind: Kind
    account_id: str
    card_id: str | None
    provisional: bool


class MovementSearch(BaseModel):
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal
    rows: list[Movement]
    rows_not_listed: int
    # Last, so a cut in the tool result drops ids before any figure.
    row_ids: list[str]


class MonthSum(BaseModel):
    month: str
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal


class MonthSums(BaseModel):
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal
    months: list[MonthSum]
    row_ids: dict[str, list[str]]


class CounterpartySum(BaseModel):
    counterparty: str
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal


class CounterpartySums(BaseModel):
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal
    counterparties: list[CounterpartySum]
    others: CounterpartySum | None
    row_ids: dict[str, list[str]]


class ProjectedMonth(BaseModel):
    month: str
    trend_chf: Decimal
    average_chf: Decimal


class MonthTrend(BaseModel):
    first_month: str
    last_month: str
    months_used: int
    average_chf: Decimal
    trend_chf_per_month: Decimal
    # None when the average is 0, since a share of nothing has no meaning.
    trend_percent_per_month: Decimal | None
    projection: list[ProjectedMonth]
    months: list[MonthSum]
    row_ids: dict[str, list[str]]


class GroupSum(BaseModel):
    group: str
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal


class GroupSums(BaseModel):
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    groups: list[GroupSum]
    row_ids: dict[str, list[str]]
