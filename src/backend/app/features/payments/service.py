import re
from typing import Any, Literal

from app.clients.banking import BankingClient
from app.core.errors import BadRequestError
from app.features.payments.schemas import BankWrite

type Method = Literal["POST", "PATCH", "DELETE"]

# Every change the model's tools may make to the bank; `{}` is one segment.
WRITES: list[tuple[Method, str]] = [
    ("POST", "/payments"),
    ("PATCH", "/payments/{}"),
    ("DELETE", "/payments/{}"),
    ("POST", "/standing-orders"),
    ("PATCH", "/standing-orders/{}"),
    ("DELETE", "/standing-orders/{}"),
]
# A segment is quoted already; `.` and `..` survive quoting and would climb to another path.
_SEGMENT = r"(?!\.\.?(?:/|$))[^/?#]+"
_WRITE_PATTERNS = [
    (method, re.compile(_SEGMENT.join(map(re.escape, path.split("{}"))))) for method, path in WRITES
]


class PaymentService:
    def __init__(self, banking: BankingClient) -> None:
        self.banking = banking

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
