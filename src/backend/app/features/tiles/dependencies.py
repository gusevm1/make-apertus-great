from typing import Annotated

from fastapi import Depends

from app.features.ledger.dependencies import LedgerServiceDep
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.service import TileService


def get_tile_service(ledger: LedgerServiceDep) -> TileService:
    return TileService(
        ledger=ledger, recurring=RecurringPaymentService(ledger=ledger)
    )


TileServiceDep = Annotated[TileService, Depends(get_tile_service)]
