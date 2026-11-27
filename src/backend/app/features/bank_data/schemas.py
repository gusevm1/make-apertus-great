from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)
ROWS_DEFAULT = 10
ROWS_MAX = 20


class BankData(RootModel[dict[str, Any]]):
    """What the banking API answered, with empty fields dropped and long lists shortened."""


class Args(BaseModel):
    # An argument the tool does not have is an error the model can correct, not a dropped filter.
    model_config = ConfigDict(extra="forbid")


class NoArgs(Args):
    pass


class Period(Args):
    # The API calls these `from` and `to`, which the model mixes up with words of the question.
    date_from: date | None = Field(
        default=None, serialization_alias="from", description=PROMPTS["date_from"]
    )
    date_to: date | None = Field(
        default=None, serialization_alias="to", description=PROMPTS["date_to"]
    )


class BalancePreviewArgs(Args):
    account_id: str = Field(description=PROMPTS["account_id"])
    date_to: date | None = Field(
        default=None, serialization_alias="to", description=PROMPTS["date_to"]
    )


class BookingsArgs(Period):
    account: list[str] | None = Field(default=None, description=PROMPTS["account_id"])
    text: str | None = Field(default=None, serialization_alias="q", description=PROMPTS["text"])
    direction: Literal["credit", "debit"] | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    sort: Literal["booking_date", "-booking_date", "amount", "-amount"] | None = None
    limit: int = Field(default=ROWS_DEFAULT, ge=1, le=ROWS_MAX, description=PROMPTS["limit"])


class PaymentsArgs(Period):
    status: Literal["pending", "completed"] | None = None
    account: str | None = Field(default=None, description=PROMPTS["account_id"])
    text: str | None = Field(default=None, serialization_alias="q", description=PROMPTS["text"])
    limit: int = Field(default=ROWS_DEFAULT, ge=1, le=ROWS_MAX, description=PROMPTS["limit"])


class UpcomingPaymentsArgs(Period):
    account: str | None = Field(default=None, description=PROMPTS["account_id"])


class PayeesArgs(Args):
    text: str | None = Field(default=None, serialization_alias="q", description=PROMPTS["text"])
    new_last_90_days: bool | None = None


class StandingOrdersArgs(Args):
    status: Literal["active", "ended"] | None = None


class CardArgs(Args):
    card_id: str = Field(description=PROMPTS["card_id"])


class CardTransactionsArgs(Period):
    card_id: str = Field(description=PROMPTS["card_id"])
    text: str | None = Field(default=None, serialization_alias="q", description=PROMPTS["text"])
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    limit: int = Field(default=ROWS_DEFAULT, ge=1, le=ROWS_MAX, description=PROMPTS["limit"])


class PortfolioPerformanceArgs(Args):
    period: Literal["ytd", "1y", "3y"] | None = None


class PortfolioTransactionsArgs(Period):
    isin: str | None = None


class LoanTransactionsArgs(Period):
    loan: str | None = None
    type: Literal["interest", "amortisation"] | None = None


class FxRatesArgs(Args):
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    currency: Literal["EUR", "USD", "GBP"] | None = None
