from datetime import date
from typing import Any

from app.clients.banking import BankingClient
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.schemas import AnyPayload, Args


class TileError(Exception):
    """A tile that cannot be drawn; the message says why, and what to send instead."""


class TileService:
    def __init__(
        self, banking: BankingClient, ledger: LedgerService, recurring: RecurringPaymentService
    ) -> None:
        self.banking = banking
        self.ledger = ledger
        self.recurring = recurring

    def validate_args(self, template: str, args: dict[str, Any]) -> Args:
        """The template's arguments as their model; TileError names what is wrong and the fix."""
        raise NotImplementedError

    async def resolve(
        self, template: str, args: dict[str, Any], token: str, today: date
    ) -> AnyPayload:
        """Compute a tile from the banking API as it is now; TileError when it has nothing to show."""
        raise NotImplementedError

    def default_title(self, payload: AnyPayload) -> str:
        """The title a tile gets when nobody wrote one, such as "Left on 23.12."."""
        raise NotImplementedError
