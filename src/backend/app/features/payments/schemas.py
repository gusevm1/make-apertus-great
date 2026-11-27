import re
from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_serializer,
    model_validator,
)

from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)
MESSAGE_MAX_CHARS = 140
# ISO 20022 limits that payment messages carry.
PAYEE_NAME_MAX_CHARS = 70
REFERENCE_MAX_CHARS = 35
_IBAN = re.compile(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}")

type Currency = Literal["CHF", "EUR", "USD", "GBP"]
type Frequency = Literal["weekly", "monthly", "quarterly", "semiannually", "annually"]


def _check_iban(iban: str) -> str:
    # ISO 13616: moving the first four characters to the end, letters as 10 to 35, leaves 1 mod 97.
    compact = iban.replace(" ", "")
    rearranged = compact[4:] + compact[:4]
    if (
        _IBAN.fullmatch(compact) is None
        or int("".join(str(int(character, 36)) for character in rearranged)) % 97 != 1
    ):
        raise ValueError(
            "Not a valid IBAN: its check digits do not match. Send it exactly as list_payees"
            " gives it, or ask the customer for it."
        )
    return iban


def _check_cents(amount: float) -> float:
    if round(amount, 2) != amount:
        raise ValueError("Send the amount with at most two decimals, such as 12.35.")
    return amount


Iban = Annotated[str, AfterValidator(_check_iban)]
Amount = Annotated[float, Field(gt=0), AfterValidator(_check_cents)]
PayeeName = Annotated[str, Field(max_length=PAYEE_NAME_MAX_CHARS)]
Reference = Annotated[str, Field(max_length=REFERENCE_MAX_CHARS)]


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
    payee_name: PayeeName | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: Iban | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: Amount
    currency: Currency
    execution_date: date = Field(description=PROMPTS["execution_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
    reference: Reference | None = Field(default=None, description=PROMPTS["reference"])

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
    payee_name: PayeeName | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: Iban | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: Amount | None = None
    currency: Currency | None = None
    execution_date: date | None = Field(default=None, description=PROMPTS["execution_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)
    reference: Reference | None = Field(default=None, description=PROMPTS["reference"])


class StandingOrderCreateArgs(Args):
    debit_account_id: str = Field(description=PROMPTS["debit_account_id"])
    credit_account_id: str | None = Field(default=None, description=PROMPTS["credit_account_id"])
    payee_name: PayeeName | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: Iban | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: Amount
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
    payee_name: PayeeName | None = Field(default=None, description=PROMPTS["payee_name"])
    payee_iban: Iban | None = Field(default=None, description=PROMPTS["payee_iban"])
    amount: Amount | None = None
    frequency: Frequency | None = None
    day: int | None = Field(default=None, ge=1, le=31, description=PROMPTS["day"])
    end_date: date | Literal["none"] | None = Field(default=None, description=PROMPTS["end_date"])
    message: str | None = Field(default=None, max_length=MESSAGE_MAX_CHARS)

    @field_serializer("end_date")
    def _none_removes_the_end_date(self, end_date: date | Literal["none"] | None) -> date | None:
        # Only this spelling clears a field; a null the model sends is dropped before the bank.
        return None if end_date == "none" else end_date
