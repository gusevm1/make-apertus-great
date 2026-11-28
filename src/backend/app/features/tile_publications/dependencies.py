from typing import Annotated

from fastapi import Depends

from app.features.boards.dependencies import BoardServiceDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.payments.dependencies import PaymentServiceDep
from app.features.tile_publications.service import TilePublicationService


def get_tile_publication_service(
    boards: BoardServiceDep, ledger: LedgerServiceDep, payments: PaymentServiceDep
) -> TilePublicationService:
    return TilePublicationService(boards=boards, ledger=ledger, payments=payments)


TilePublicationServiceDep = Annotated[TilePublicationService, Depends(get_tile_publication_service)]
