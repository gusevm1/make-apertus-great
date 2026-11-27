from decimal import Decimal
from typing import Any

from app.clients.banking import BankingClient
from app.features.ledger.schemas import Kind, LedgerRow

PAGE_SIZE = 1000  # the banking API's maximum
OWN_TRANSFER_TYPES = {"account_transfer", "securities_buy"}


class LedgerService:
    def __init__(self, banking: BankingClient) -> None:
        self.banking = banking

    async def rows(self, token: str) -> list[LedgerRow]:
        """Every booking and credit card purchase of the customer, oldest first."""
        accounts = await self.banking.get(path="/accounts", token=token)
        own_ibans = {_compact(iban=account["iban"]) for account in accounts["items"]}
        charges = await self.banking.get(path="/loan-transactions", token=token)
        charge_by_booking = {charge["booking_id"]: charge for charge in charges["items"]}

        rows = [
            _booking_row(
                booking=booking,
                own_ibans=own_ibans,
                loan_charge=charge_by_booking.get(booking["booking_id"]),
            )
            for booking in await self._all_pages(path="/bookings", token=token)
        ]
        cards = await self.banking.get(path="/cards", token=token)
        for card in cards["items"]:
            # Debit card payments are bookings already; only a credit card has its own list.
            if card["type"] != "credit":
                continue
            purchases = await self._all_pages(
                path=f"/cards/{card['card_id']}/transactions", token=token
            )
            rows += [
                _card_row(purchase=purchase, account_id=card["linked_account"])
                for purchase in purchases
            ]
        return sorted(rows, key=lambda row: (row.date, row.id))

    async def _all_pages(self, path: str, token: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            page = await self.banking.get(
                path=path, token=token, params={"limit": PAGE_SIZE, "offset": len(items)}
            )
            items += page["items"]
            if len(items) >= page["total"] or not page["items"]:
                return items


def _booking_row(
    booking: dict[str, Any], own_ibans: set[str], loan_charge: dict[str, Any] | None
) -> LedgerRow:
    is_settlement = booking["transaction_type"] == "card_settlement"
    return LedgerRow(
        source="booking",
        id=booking["booking_id"],
        account_id=booking["account_id"],
        card_id=booking.get("card_id"),
        date=booking["booking_date"],
        amount_chf=_chf(amount=booking["amount"]),
        text=booking["booking_text"],
        counterparty=booking.get("counterparty_name"),
        transaction_type=booking["transaction_type"],
        original_amount=_chf_or_none(amount=booking.get("original_amount")),
        original_currency=booking.get("original_currency"),
        # The bank puts the statement id of a card bill into the reference.
        statement_id=booking.get("reference") if is_settlement else None,
        loan_id=None if loan_charge is None else loan_charge["loan_id"],
        loan_charge=None if loan_charge is None else loan_charge["type"],
        kind=_booking_kind(booking=booking, own_ibans=own_ibans),
    )


def _booking_kind(booking: dict[str, Any], own_ibans: set[str]) -> Kind:
    if booking["transaction_type"] == "card_settlement":
        return "card_settlement"
    iban = booking.get("counterparty_iban")
    to_own_account = iban is not None and _compact(iban=iban) in own_ibans
    if booking["transaction_type"] in OWN_TRANSFER_TYPES or to_own_account:
        return "own_transfer"
    return "credit" if booking["amount"] > 0 else "spending"


def _card_row(purchase: dict[str, Any], account_id: str) -> LedgerRow:
    # The card lists a charge as positive; the ledger uses the sign of a booking.
    amount = -_chf(amount=purchase["amount_chf"])
    original = _chf_or_none(amount=purchase.get("original_amount"))
    return LedgerRow(
        source="card_transaction",
        id=purchase["card_transaction_id"],
        account_id=account_id,
        card_id=purchase["card_id"],
        date=purchase["transaction_date"],
        amount_chf=amount,
        text=purchase["merchant_text"],
        counterparty=purchase.get("merchant_name"),
        original_amount=None if original is None else -original,
        original_currency=purchase.get("original_currency"),
        statement_id=purchase.get("statement_id"),
        kind="credit" if amount > 0 else "spending",
    )


def _compact(iban: str) -> str:
    return iban.replace(" ", "").upper()


def _chf(amount: float) -> Decimal:
    # Through str, so 0.1 stays 0.1 and sums add up to the cent.
    return Decimal(str(amount))


def _chf_or_none(amount: float | None) -> Decimal | None:
    return None if amount is None else _chf(amount=amount)
