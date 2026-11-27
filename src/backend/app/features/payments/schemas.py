from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)
MESSAGE_MAX_CHARS = 140

type Currency = Literal["CHF", "EUR", "USD", "GBP"]
type Frequency = Literal["weekly", "monthly", "quarterly", "semiannually", "annually"]


class BankWrite(RootModel[dict[str, Any]]):
    """What the banking API answered to a change."""


class Args(BaseModel):
    # The sheet lists the arguments as sent, so nothing the bank would not see may pass.
    model_config = ConfigDict(extra="forbid")


class Change(Args):
    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if len(self.model_dump(exclude_none=True)) < 2:
            raise ValueError("Name at least one field to change besides the id.")
        return self


class Address(Args):
    street: str
    zip: str
    city: str
    country: str = Field(description=PROMPTS["country"])


class PaymentCreateArgs(Args):
    payment_type: Literal["domestic", "qr_bill", "international", "account_transfer"] = Field(
        description=PROMPTS["payment_type"]
    )
    debit_account_id: str = Field(description=PROMPTS["debit_account_id"])
    credit_account_id: str | None = Field(default=None, description=PROMPTS["credit_account_id"])
    payee_name: str | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: str | None = Field(default=None, description=PROMPTS["payee_iban"])
    payee_address: Address | None = None
    amount: float = Field(gt=0)
    currency: Currency
    execution_date: date = Field(description=PROMPTS["execution_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
    reference: str | None = Field(default=None, description=PROMPTS["reference"])


class PaymentArgs(Args):
    payment_id: str = Field(description=PROMPTS["payment_id"])


class PaymentUpdateArgs(Change, PaymentArgs):
    debit_account_id: str | None = Field(default=None, description=PROMPTS["debit_account_id"])
    credit_account_id: str | None = Field(default=None, description=PROMPTS["credit_account_id"])
    payee_name: str | None = None
    payee_iban: str | None = None
    payee_address: Address | None = None
    amount: float | None = Field(default=None, gt=0)
    currency: Currency | None = None
    execution_date: date | None = Field(default=None, description=PROMPTS["execution_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
    reference: str | None = None


class StandingOrderCreateArgs(Args):
    debit_account_id: str = Field(description=PROMPTS["debit_account_id"])
    credit_account_id: str | None = Field(default=None, description=PROMPTS["credit_account_id"])
    payee_name: str | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: str | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: float = Field(gt=0)
    currency: Currency
    frequency: Frequency
    day: int | None = Field(default=None, ge=1, le=31, description=PROMPTS["day"])
    start_date: date
    end_date: date | None = None
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)


class StandingOrderArgs(Args):
    standing_order_id: str = Field(description=PROMPTS["standing_order_id"])


class StandingOrderUpdateArgs(Change, StandingOrderArgs):
    payee_name: str | None = None
    payee_iban: str | None = None
    amount: float | None = Field(default=None, gt=0)
    frequency: Frequency | None = None
    day: int | None = Field(default=None, ge=1, le=31, description=PROMPTS["day"])
    end_date: date | None = None
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
