import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

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
