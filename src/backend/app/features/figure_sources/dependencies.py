from typing import Annotated

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.features.figure_checks.dependencies import FigureCheckServiceDep
from app.features.figure_sources.service import FigureSourceService
from app.features.ledger.dependencies import LedgerServiceDep


def get_figure_source_service(
    figure_checks: FigureCheckServiceDep, ledger: LedgerServiceDep, user: CurrentUserDep
) -> FigureSourceService:
    return FigureSourceService(figure_checks=figure_checks, ledger=ledger, token=user.token)


FigureSourceServiceDep = Annotated[FigureSourceService, Depends(get_figure_source_service)]
