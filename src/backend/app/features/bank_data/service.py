import json
from datetime import date
from typing import Any

from app.features.bank_data.schemas import BankData
from app.features.ledger.service import LedgerService

# The tool loop cuts a result at 6000 characters; rows stop earlier so the sums always fit.
ROWS_MAX_CHARS = 5000
ROW_LISTS = ("items", "points")


class BankDataService:
    def __init__(self, ledger: LedgerService) -> None:
        self.ledger = ledger

    async def read(self, path: str, token: str, params: dict[str, Any]) -> BankData:
        """One read from the banking API as the customer, shortened to fit a tool result."""
        data = await self.ledger.read(path=path, token=token, params=params)
        return BankData(root=fit(data=data))

    async def list_upcoming_payments(
        self, token: str, date_from: date | None, date_to: date | None
    ) -> dict[str, Any]:
        """The bank's upcoming payments as it lists them; without dates, its next 60 days."""
        params = {
            name: value.isoformat()
            for name, value in {"from": date_from, "to": date_to}.items()
            if value is not None
        }
        return await self.ledger.read(path="/upcoming-payments", token=token, params=params)


def fit(data: dict[str, Any]) -> dict[str, Any]:
    """Drops empty fields and lists only the rows there is room for, counting the rest."""
    fitted = _without_empty(value=data)
    for key in ROW_LISTS:
        rows = fitted.get(key)
        if not isinstance(rows, list):
            continue
        used, kept = 0, 0
        for row in rows:
            used += len(json.dumps(row, ensure_ascii=False))
            if used > ROWS_MAX_CHARS:
                break
            kept += 1
        if kept < len(rows):
            fitted[key] = rows[:kept]
            fitted[f"{key}_not_listed"] = len(rows) - kept
    return fitted


def _without_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_empty(value=item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_empty(value=item) for item in value]
    return value
