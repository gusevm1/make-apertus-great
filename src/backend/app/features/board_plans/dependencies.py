from typing import Annotated

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.features.board_plans.service import BoardPlanService
from app.features.figure_checks.dependencies import FigureCheckServiceDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.recurring_payments.dependencies import RecurringPaymentServiceDep
from app.features.tiles.dependencies import TileServiceDep


def get_board_plan_service(
    apertus: ApertusClientDep,
    tiles: TileServiceDep,
    ledger: LedgerServiceDep,
    recurring: RecurringPaymentServiceDep,
    figure_checks: FigureCheckServiceDep,
) -> BoardPlanService:
    return BoardPlanService(
        apertus=apertus,
        tiles=tiles,
        ledger=ledger,
        recurring=recurring,
        figure_checks=figure_checks,
    )


BoardPlanServiceDep = Annotated[BoardPlanService, Depends(get_board_plan_service)]
