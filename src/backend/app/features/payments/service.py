import re
from typing import Any, Literal

from pydantic import BaseModel

from app.clients.banking import BankingClient
from app.core.errors import BadRequestError
from app.core.tools import SheetLine
from app.features.ledger.service import PAGE_SIZE, LedgerService
from app.features.payments import sheet
from app.features.payments.schemas import BankWrite

type Method = Literal["POST", "PATCH", "DELETE"]

# Every change TrustRoom may make to the bank, each after the customer's click; `{}` is one
# segment. The dashboard widgets are #26's "Put on dashboard", which no tool of the model calls.
WRITES: list[tuple[Method, str]] = [
    ("POST", "/payments"),
    ("PATCH", "/payments/{}"),
    ("DELETE", "/payments/{}"),
    ("POST", "/standing-orders"),
    ("PATCH", "/standing-orders/{}"),
    ("DELETE", "/standing-orders/{}"),
    ("POST", "/dashboards/{}/widgets"),
    ("PATCH", "/dashboards/{}/widgets/{}"),
]
# A segment is quoted already; `.` and `..` survive quoting and would climb to another path.
_SEGMENT = r"(?!\.\.?(?:/|$))[^/?#]+"
# Per id argument: where the sheet finds its item, and what the model reads to find a right one.
ITEMS = {
    "payment_id": (
        "/payments",
        {"status": "pending", "limit": PAGE_SIZE},
        "pending payments. Send a payment_id from list_payments with status pending.",
    ),
    "standing_order_id": (
        "/standing-orders",
        None,
        "standing orders. Send a standing_order_id from list_standing_orders.",
    ),
}
_WRITE_PATTERNS = [
    (method, re.compile(_SEGMENT.join(map(re.escape, path.split("{}"))))) for method, path in WRITES
]


class PaymentService:
    def __init__(self, banking: BankingClient, ledger: LedgerService) -> None:
        self.banking = banking
        self.ledger = ledger

    async def sheet(self, args: BaseModel, token: str) -> list[SheetLine]:
        """The confirmation sheet of a write; an id that is not the customer's is refused."""
        values = args.model_dump(mode="json", exclude_none=True)
        listed = await self.ledger.read(path="/accounts", token=token)
        accounts = {account["account_id"]: account for account in listed["items"]}
        for field in sheet.ACCOUNT_FIELDS & values.keys():
            if values[field] not in accounts:
                raise BadRequestError(
                    f"{field} {values[field]} is not one of the customer's accounts."
                    " Send an account_id from list_accounts."
                )
        item = None
        for field in ITEMS.keys() & values.keys():
            path, params, hint = ITEMS[field]
            listed = await self.ledger.read(path=path, token=token, params=params)
            item = next((row for row in listed["items"] if row[field] == values[field]), None)
            if item is None:
                raise BadRequestError(f"{values[field]} is not one of the customer's {hint}")
        return sheet.lines(values=values, accounts=accounts, item=item)

    async def write(
        self, method: Method, path: str, token: str, body: dict[str, Any] | None
    ) -> BankWrite:
        """One change to the bank as the customer, only one of `WRITES`; call it after their yes."""
        if not any(
            method == allowed and pattern.fullmatch(path) for allowed, pattern in _WRITE_PATTERNS
        ):
            raise BadRequestError(f"{method} {path} is not a change the payments allow")
        answer = await self.banking.write(method=method, path=path, token=token, body=body)
        return BankWrite(root={"deleted": path} if answer is None else answer)
