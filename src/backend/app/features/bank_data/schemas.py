from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

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

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        # The bank answers a period that ends before it starts with no rows, which reads as "none".
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from is after date_to. The period starts on date_from.")
        return self


class BalancePreviewArgs(Args):
    account_id: str = Field(description=PROMPTS["account_id"])
    date_to: date | None = Field(
        default=None, serialization_alias="to", description=PROMPTS["date_to"]
    )


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


class PortfolioPerformanceArgs(Args):
    period: Literal["ytd", "1y", "3y"] | None = None


class PortfolioTransactionsArgs(Period):
    isin: str | None = None


class LoanTransactionsArgs(Period):
    loan: str | None = None
    type: Literal["interest", "amortisation"] | None = None


class FxRatesArgs(Args):
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    currency: Literal["CHF", "EUR", "USD", "GBP"] | None = None

    @field_validator("currency")
    @classmethod
    def _chf_is_the_base(cls, currency: str | None) -> str | None:
        # Every rate is quoted in CHF, so asking for CHF means asking for all of them.
        if currency == "CHF":
            return None
        return currency
