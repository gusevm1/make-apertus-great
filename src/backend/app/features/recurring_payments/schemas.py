import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

Cadence = Literal["monthly", "quarterly", "yearly"]


# Amounts here are what the customer paid, as positive numbers.
class PriceChange(BaseModel):
    date: datetime.date
    old_price: Decimal
    new_price: Decimal
    currency: str
    id_before: str
    id_after: str


class RecurringPayment(BaseModel):
    payee: str
    cadence: Cadence
    payments: int
    last_date: datetime.date
    last_paid_chf: Decimal
    paid_last_12_months_chf: Decimal  # the sum of real payments, not a projection
    next_expected: datetime.date
    active: bool
    price_changes: list[PriceChange]
    ids: list[str]


class InstalmentPlan(BaseModel):
    payee: str
    plan: str
    instalment_chf: Decimal
    paid: int
    total: int
    left: int
    left_chf: Decimal
    last_date: datetime.date
    ids: list[str]


class RecurringPayments(BaseModel):
    recurring: list[RecurringPayment]
    instalment_plans: list[InstalmentPlan]
