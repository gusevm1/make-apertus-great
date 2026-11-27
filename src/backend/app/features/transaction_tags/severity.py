from app.features.ledger.schemas import LedgerRow
from app.features.transaction_tags.schemas import SeveritySource

# What a category counts for when neither the customer nor Apertus said anything about it.
DEFAULT_SEVERITY = {
    "housing": "critical",
    "groceries": "critical",
    "health": "critical",
    "insurance": "critical",
    "loan_leasing": "critical",
    "taxes": "critical",
    "children": "major",
    "transport": "major",
    "leisure_travel": "moderate",
    "subscriptions_media": "moderate",
    "shopping": "moderate",
    "restaurants": "minor",
    "other": "moderate",
}


def payee_key(row: LedgerRow) -> str:
    """The payee of a ledger row: its counterparty, else its text."""
    return normalise_payee(name=row.text if row.counterparty is None else row.counterparty)


def normalise_payee(name: str) -> str:
    return " ".join(name.lower().split())


def booking_key(row_source: str, row_id: str) -> str:
    return f"{row_source}:{row_id}"


def effective_severity(
    category: str, booking: str, payee: str | None, stored: dict[tuple[str, str], str]
) -> tuple[str, SeveritySource]:
    """The severity of a row: its own override, its payee's, its category's, else the default."""
    if (booking_severity := stored.get(("booking", booking))) is not None:
        return booking_severity, "booking"
    if payee is not None and (payee_severity := stored.get(("payee", payee))) is not None:
        return payee_severity, "payee"
    if (category_severity := stored.get(("category", category))) is not None:
        return category_severity, "category"
    return DEFAULT_SEVERITY[category], "default"
