from datetime import date
from typing import Any

from app.core.tools import SheetLine

# The sheet's label per field, in the order the sheet lists them.
LABELS = {
    "payment_type": "Type",
    "debit_account_id": "Debit account",
    "payee_name": "Payee",
    "payee_iban": "IBAN",
    "credit_account_id": "Receiving account",
    "amount": "Amount",
    "currency": "Currency",
    "execution_date": "Date",
    "frequency": "Frequency",
    "day": "Day of the month",
    "start_date": "Start date",
    "end_date": "End date",
    "next_execution_date": "Next payment",
    "message": "Message",
    "reference": "Reference",
}
# They name the payment or standing order, which the sheet shows instead.
IDS = {"payment_id", "standing_order_id"}
ACCOUNT_FIELDS = {"debit_account_id", "credit_account_id"}
DATE_FIELDS = {"execution_date", "start_date", "end_date", "next_execution_date"}
PAYMENT_TYPES = {
    "domestic": "Domestic payment",
    "qr_bill": "QR bill",
    "international": "International payment",
    "account_transfer": "Transfer between own accounts",
    "ebill": "eBill",
}


# 1250 → "CHF 1'250.00", as the e-banking writes it.
def money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}".replace(",", "'")


# 2026-12-01 → "01.12.2026".
def day(value: str) -> str:
    return date.fromisoformat(value).strftime("%d.%m.%Y")


# What a write sends; for a change or a delete, the item as it will be, changes marked.
def lines(
    values: dict[str, Any], accounts: dict[str, dict[str, Any]], item: dict[str, Any] | None
) -> list[SheetLine]:
    before = (
        {} if item is None else {field: value for field, value in item.items() if value is not None}
    )
    after = {**before, **values}
    fields = [field for field in LABELS if field in after]
    fields += [field for field in values if field not in LABELS and field not in IDS]
    currency = after.get("currency", "CHF")
    shown = []
    for field in fields:
        is_changed = item is not None and field in values and before.get(field) != values[field]
        # The amount line names the currency.
        if field == "currency" and "amount" in after and not is_changed:
            continue
        text = _text(field=field, value=after[field], currency=currency, accounts=accounts)
        detail = _iban(field=field, value=after[field], accounts=accounts)
        if is_changed:
            old = before.get(field)
            detail = (
                "New"
                if old is None
                else f"Was {_text(field=field, value=old, currency=currency, accounts=accounts)}"
            )
        label = LABELS.get(field, field.replace("_", " ").capitalize())
        shown.append(SheetLine(label=label, value=text, detail=detail))
    return shown


def _text(field: str, value: Any, currency: str, accounts: dict[str, dict[str, Any]]) -> str:
    # end_date "none" reaches the bank as null and removes the end date.
    if field == "end_date" and value is None:
        return "No end date"
    if field in ACCOUNT_FIELDS:
        return accounts[value]["name"] if value in accounts else str(value)
    if field == "amount":
        return money(amount=value, currency=currency)
    if field in DATE_FIELDS:
        return day(value=value)
    if field == "payment_type":
        return PAYMENT_TYPES.get(value, str(value))
    if field == "frequency":
        return value.capitalize()
    return str(value)


def _iban(field: str, value: Any, accounts: dict[str, dict[str, Any]]) -> str | None:
    if field not in ACCOUNT_FIELDS or value not in accounts:
        return None
    return accounts[value]["iban"]
