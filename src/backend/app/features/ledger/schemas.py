import datetime
import re
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
# Today's salary level is the median of the last months; a month below this share of it is lower.
SALARY_LEVEL_MONTHS = 3
SALARY_LEVEL_SHARE = Decimal("0.5")
PERIOD_FIELDS = ("first_from", "first_to", "second_from", "second_to")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Per side of a balance change; the rest is added up as `others`.
TOP_BALANCE_COUNTERPARTIES = 5
PILLAR_3A_COUNTERPARTY = "Säule 3a"
# The largest Pillar 3a payment a year for an employee with a pension fund.
PILLAR_3A_LIMITS_CHF = {2024: Decimal("7056"), 2025: Decimal("7258"), 2026: Decimal("7258")}

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
    # Only a booking carries the account's balance after it.
    balance_after_chf: Decimal | None = None
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


class ComparePeriodsArgs(Selection):
    first_from: datetime.date | None = Field(default=None, description=PROMPTS["first_from"])
    first_to: datetime.date | None = Field(default=None, description=PROMPTS["first_to"])
    second_from: datetime.date | None = Field(default=None, description=PROMPTS["second_from"])
    second_to: datetime.date | None = Field(default=None, description=PROMPTS["second_to"])
    since_salary_start: bool = Field(default=False, description=PROMPTS["since_salary_start"])

    @model_validator(mode="before")
    @classmethod
    def _salary_start_needs_no_dates(cls, data: Any) -> Any:
        # Without known dates the model writes placeholders; here the server finds the dates.
        if isinstance(data, dict) and str(data.get("since_salary_start")).lower() == "true":
            return {key: value for key, value in data.items() if key not in PERIOD_FIELDS}
        return data

    @field_validator(*PERIOD_FIELDS, mode="before")
    @classmethod
    def _a_date(cls, value: Any) -> Any:
        # The model writes placeholders when it plans this call before it knows the date.
        if isinstance(value, str) and DATE.fullmatch(value) is None:
            raise ValueError(PROMPTS["not_a_date"].format(value=value))
        return value

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        if self.since_salary_start:
            return self
        for (start, end), name in zip(self.periods(), ["first", "second"], strict=True):
            if start > end:
                raise ValueError(
                    f"{name}_from is after {name}_to. The period starts on {name}_from."
                )
        return self

    def periods(self) -> list[tuple[datetime.date, datetime.date]]:
        if (
            self.first_from is None
            or self.first_to is None
            or self.second_from is None
            or self.second_to is None
        ):
            raise ValueError(PROMPTS["dates_or_salary_start"])
        return [(self.first_from, self.first_to), (self.second_from, self.second_to)]


class BalanceChangeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(description=PROMPTS["account_id"])
    date_from: datetime.date = Field(description=PROMPTS["balance_date_from"])
    date_to: datetime.date = Field(description=PROMPTS["balance_date_to"])

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        if self.date_from > self.date_to:
            raise ValueError("date_from is after date_to. The period starts on date_from.")
        return self


class TaxYearArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=2000, le=2100, description=PROMPTS["tax_year"])


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


Reason = Literal["unusual_amount", "first_payment", "same_day_twice"]


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


class UnusualMovement(BaseModel):
    reason: Reason
    movement: Movement
    # For unusual_amount: the median of the counterparty's earlier payments and how many there were.
    typical_chf: Decimal | None = None
    typical_count: int | None = None


class UnusualMovements(BaseModel):
    # The period checked; None is open at that end.
    date_from: datetime.date | None
    date_to: datetime.date | None
    checked: int
    flagged: int
    not_listed: int
    movements: list[UnusualMovement]
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
    # Over every month of the period, a month without a match counting as 0.
    average_out_chf: Decimal
    average_in_chf: Decimal
    # None when no money moved that way in the whole period.
    month_most_out: MonthSum | None
    month_least_out: MonthSum | None
    month_most_in: MonthSum | None
    month_least_in: MonthSum | None
    months: list[MonthSum]
    row_ids: dict[str, list[str]]


class PeriodSum(BaseModel):
    date_from: datetime.date
    date_to: datetime.date
    months: int
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal
    average_out_chf: Decimal
    average_in_chf: Decimal


class PeriodComparison(BaseModel):
    earlier: PeriodSum
    later: PeriodSum
    # Positive means more money moved that way in the later period than in the earlier one.
    money_out_change_chf: Decimal
    money_out_change_percent: Decimal | None
    money_in_change_chf: Decimal
    money_in_change_percent: Decimal | None
    # The change of the average per month, which compares periods of different length.
    average_out_change_chf: Decimal
    average_out_change_percent: Decimal | None
    average_in_change_chf: Decimal
    average_in_change_percent: Decimal | None
    # With since_salary_start: the first salary at today's level, where the later period begins.
    salary_start: datetime.date | None = None
    # Last, so a cut in the tool result drops ids before any figure.
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
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal


class GroupSums(BaseModel):
    count: int
    money_out_chf: Decimal
    money_in_chf: Decimal
    provisional_out_chf: Decimal
    provisional_in_chf: Decimal
    groups: list[GroupSum]
    row_ids: dict[str, list[str]]


class BalanceChange(BaseModel):
    account_id: str
    date_from: datetime.date
    date_to: datetime.date
    # Before the first booking of date_from, and after the last booking of date_to.
    start_balance_chf: Decimal
    end_balance_chf: Decimal
    change_chf: Decimal
    count: int
    money_in_chf: Decimal
    money_out_chf: Decimal
    # 0 when start plus money in plus money out (negative) gives the end balance.
    unexplained_chf: Decimal
    largest_in: list[CounterpartySum]
    others_in: CounterpartySum | None
    largest_out: list[CounterpartySum]
    others_out: CounterpartySum | None
    # Last, so a cut in the tool result drops ids before any figure.
    row_ids: dict[str, dict[str, list[str]]]


class YearEndBalance(BaseModel):
    account_id: str
    # The day of the account's last booking on or before 31 December.
    date: datetime.date
    balance_chf: Decimal


class TaxYearSummary(BaseModel):
    year: int
    # Before 31 December when the year is not over yet.
    until: datetime.date
    mortgage_interest_paid_chf: Decimal
    pillar_3a_paid_chf: Decimal
    # None for a year whose limit the server does not know.
    pillar_3a_limit_chf: Decimal | None
    pillar_3a_over_limit_chf: Decimal | None
    year_end_balances: list[YearEndBalance]
    # On 31 December; None when the portfolio's history has no value for that day.
    portfolio_value_chf: Decimal | None
    note: str
    # Last, so a cut in the tool result drops ids before any figure.
    row_ids: dict[str, list[str]]
