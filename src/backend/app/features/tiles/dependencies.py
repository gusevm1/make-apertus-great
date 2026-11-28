from typing import Annotated

from fastapi import Depends

from app.clients.banking import BankingClientDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.service import TileService


def get_tile_service(banking: BankingClientDep, ledger: LedgerServiceDep) -> TileService:
    return TileService(
        banking=banking, ledger=ledger, recurring=RecurringPaymentService(ledger=ledger)
    )


TileServiceDep = Annotated[TileService, Depends(get_tile_service)]
