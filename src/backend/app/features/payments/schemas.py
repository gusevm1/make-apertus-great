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


def _check_recipient(credit_account_id: str | None, payee: list[str | None], is_own: bool) -> None:
    # The bank refuses these too, but only after the customer has allowed a call that cannot work.
    if is_own and credit_account_id is None:
        raise ValueError("A transfer between own accounts needs credit_account_id.")
    if not is_own and None in payee:
        raise ValueError(
            "Send payee_name and payee_iban as list_payees gives them (without text it lists"
            " every payee), or credit_account_id for one of the customer's own accounts."
        )


class PaymentCreateArgs(Args):
    payment_type: Literal["domestic", "qr_bill", "international", "account_transfer"] = Field(
        description=PROMPTS["payment_type"]
    )
    debit_account_id: str = Field(description=PROMPTS["debit_account_id"])
    credit_account_id: str | None = Field(default=None, description=PROMPTS["credit_account_id"])
    payee_name: str | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: str | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: float = Field(gt=0)
    currency: Currency
    execution_date: date = Field(description=PROMPTS["execution_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
    reference: str | None = Field(default=None, description=PROMPTS["reference"])

    @model_validator(mode="after")
    def _has_a_recipient(self) -> Self:
        _check_recipient(
            credit_account_id=self.credit_account_id,
            payee=[self.payee_name, self.payee_iban],
            is_own=self.payment_type == "account_transfer",
        )
        return self


class PaymentArgs(Args):
    payment_id: str = Field(description=PROMPTS["payment_id"])


class PaymentUpdateArgs(Change, PaymentArgs):
    debit_account_id: str | None = Field(default=None, description=PROMPTS["debit_account_id"])
    credit_account_id: str | None = Field(default=None, description=PROMPTS["credit_account_id"])
    payee_name: str | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: str | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: float | None = Field(default=None, gt=0)
    currency: Currency | None = None
    execution_date: date | None = Field(default=None, description=PROMPTS["execution_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
    reference: str | None = Field(default=None, description=PROMPTS["reference"])


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

    @model_validator(mode="after")
    def _has_a_recipient(self) -> Self:
        _check_recipient(
            credit_account_id=self.credit_account_id,
            payee=[self.payee_name, self.payee_iban],
            is_own=self.payee_iban is None and self.credit_account_id is not None,
        )
        return self


class StandingOrderArgs(Args):
    standing_order_id: str = Field(description=PROMPTS["standing_order_id"])


class StandingOrderUpdateArgs(Change, StandingOrderArgs):
    payee_name: str | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: str | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: float | None = Field(default=None, gt=0)
    frequency: Frequency | None = None
    day: int | None = Field(default=None, ge=1, le=31, description=PROMPTS["day"])
    end_date: date | None = None
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
