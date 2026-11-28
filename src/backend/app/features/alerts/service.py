from datetime import date, timedelta
from decimal import Decimal
from typing import Any, get_args
from uuid import UUID

from app.core.errors import NotFoundError
from app.features.alerts.repository import AlertDismissalRepository, AlertSettingRepository
from app.features.alerts.schemas import (
    AMOUNT_TOLERANCE_CHF,
    DEFAULT_ENABLED,
    PENDING_PAYMENTS_LIMIT,
    UNDATED_LOOKBACK_DAYS,
    Alert,
    AlertDismissal,
    AlertKind,
    AlertSetting,
)
from app.features.documents.schemas import Document
from app.features.documents.service import DocumentService
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService


class AlertService:
    def __init__(
        self,
        dismissals: AlertDismissalRepository,
        settings: AlertSettingRepository,
        documents: DocumentService,
        ledger: LedgerService,
    ) -> None:
        self.dismissals = dismissals
        self.settings = settings
        self.documents = documents
        self.ledger = ledger

    async def list_alerts(self, owner_id: UUID, token: str) -> list[Alert]:
        """The flags that are open now, computed from documents, bookings and pending payments."""
        enabled = {
            setting.kind: setting.enabled for setting in await self.list_settings(owner_id=owner_id)
        }
        if not enabled["invoice"]:
            return []
        documents = await self.documents.list_documents(owner_id=owner_id)
        dismissed = {dismissal.key for dismissal in await self.dismissals.list(owner_id=owner_id)}
        bills = [bill for bill in _bills(documents=documents) if bill.key not in dismissed]
        if not bills:
            return []
        today = await self.ledger.get_today()
        rows = await self.ledger.list_rows(token=token)
        pending = await self.ledger.read(
            path="/payments",
            token=token,
            params={"status": "pending", "limit": PENDING_PAYMENTS_LIMIT},
        )
        pending_amounts = [_payment_chf(payment=payment) for payment in pending["items"]]
        open_bills = [
            bill
            for bill in bills
            if not _is_paid(bill=bill, rows=rows, today=today)
            and not any(
                _same_amount(first=amount, second=bill.amount_chf) for amount in pending_amounts
            )
        ]
        return sorted(open_bills, key=lambda bill: (bill.due_date is None, bill.due_date))

    async def list_dismissals(self, owner_id: UUID) -> list[AlertDismissal]:
        """Every flag the customer marked done."""
        return await self.dismissals.list(owner_id=owner_id)

    async def create_dismissal(self, owner_id: UUID, key: str) -> AlertDismissal:
        """Hide one flag for good."""
        return await self.dismissals.add(owner_id=owner_id, key=key)

    async def get_dismissal(self, dismissal_id: UUID, owner_id: UUID) -> AlertDismissal:
        dismissal = await self.dismissals.get_owned(dismissal_id=dismissal_id, owner_id=owner_id)
        if dismissal is None:
            raise NotFoundError("Dismissal not found")
        return dismissal

    async def delete_dismissal(self, dismissal_id: UUID) -> None:
        """Show the flag again while it is open."""
        await self.dismissals.delete(entity_id=dismissal_id)

    async def list_settings(self, owner_id: UUID) -> list[AlertSetting]:
        """Every check, on or off, with the default where the customer chose nothing."""
        stored = {
            setting.kind: setting.enabled for setting in await self.settings.list(owner_id=owner_id)
        }
        return [
            AlertSetting(kind=kind, enabled=stored.get(kind, DEFAULT_ENABLED[kind]))
            for kind in get_args(AlertKind)
        ]

    async def update_setting(self, owner_id: UUID, kind: AlertKind, enabled: bool) -> AlertSetting:
        """Turn a check on or off."""
        return await self.settings.upsert(owner_id=owner_id, kind=kind, enabled=enabled)

    async def delete_setting(self, owner_id: UUID, kind: AlertKind) -> None:
        """Put a check back to its default."""
        await self.settings.delete_kind(owner_id=owner_id, kind=kind)


# One flag per bill: an invoice and its reminder for the same payee and amount count once.
def _bills(documents: list[Document]) -> list[Alert]:
    bills: dict[tuple[str, Decimal], Alert] = {}
    for document in documents:
        bill = _bill(document=document)
        if bill is None:
            continue
        same = ((bill.payee or "").casefold(), bill.amount_chf)
        # Documents come newest first, so the reminder wins over the invoice it repeats.
        bills.setdefault(same, bill)
    return list(bills.values())


def _bill(document: Document) -> Alert | None:
    if document.kind != "invoice" and document.kind != "reminder":
        return None
    fields = {field.name: field for field in document.fields}
    amount = fields.get("amount_due")
    if amount is None or amount.amount is None:
        return None
    if amount.currency is not None and amount.currency.upper() != "CHF":
        return None
    payee = fields.get("payee")
    due = fields.get("due_date")
    return Alert(
        key=f"invoice:{document.id}",
        kind="invoice",
        document_id=document.id,
        document_name=document.name,
        document_kind=document.kind,
        payee=payee.text if payee is not None and payee.text is not None else document.issuer,
        amount_chf=Decimal(str(amount.amount)).quantize(Decimal("0.01")),
        due_date=due.date if due is not None else None,
        document_date=document.document_date,
    )


def _is_paid(bill: Alert, rows: list[LedgerRow], today: date) -> bool:
    since = bill.document_date
    if since is None:
        since = today - timedelta(days=UNDATED_LOOKBACK_DAYS)
    return any(
        row.amount_chf < 0
        and since <= row.date <= today
        and _same_amount(first=-row.amount_chf, second=bill.amount_chf)
        for row in rows
    )


def _payment_chf(payment: dict[str, Any]) -> Decimal | None:
    if payment.get("amount_chf") is not None:
        return Decimal(str(payment["amount_chf"]))
    if payment.get("currency") == "CHF":
        return Decimal(str(payment["amount"]))
    return None


def _same_amount(first: Decimal | None, second: Decimal) -> bool:
    return first is not None and abs(first - second) <= AMOUNT_TOLERANCE_CHF
