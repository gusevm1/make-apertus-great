from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.figure_checks.dependencies import FigureCheckServiceDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.payments.dependencies import PaymentServiceDep
from app.features.widgets.repository import WidgetRepository, WidgetVersionRepository
from app.features.widgets.schemas import Widget
from app.features.widgets.service import WidgetService


def get_widget_service(
    session: SessionDep,
    apertus: ApertusClientDep,
    figure_checks: FigureCheckServiceDep,
    ledger: LedgerServiceDep,
    payments: PaymentServiceDep,
) -> WidgetService:
    return WidgetService(
        widgets=WidgetRepository(session=session),
        versions=WidgetVersionRepository(session=session),
        apertus=apertus,
        figure_checks=figure_checks,
        ledger=ledger,
        payments=payments,
    )


WidgetServiceDep = Annotated[WidgetService, Depends(get_widget_service)]


async def get_owned_widget(
    widget_id: UUID, user: CurrentUserDep, service: WidgetServiceDep
) -> Widget:
    return await service.get_widget(widget_id=widget_id, owner_id=user.id)


OwnedWidgetDep = Annotated[Widget, Depends(get_owned_widget)]
