from decimal import Decimal

from pydantic import BaseModel


class AccountBalance(BaseModel):
    account_id: str
    name: str
    type: str
    iban: str
    balance_chf: Decimal


class AccountBalances(BaseModel):
    accounts: list[AccountBalance]
    total_balance_chf: Decimal
