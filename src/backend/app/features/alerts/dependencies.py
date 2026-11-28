from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.alerts.repository import AlertDismissalRepository, AlertSettingRepository
from app.features.alerts.schemas import AlertDismissal
from app.features.alerts.service import AlertService
from app.features.documents.dependencies import DocumentServiceDep
from app.features.ledger.dependencies import LedgerServiceDep


def get_alert_service(
    session: SessionDep, documents: DocumentServiceDep, ledger: LedgerServiceDep
) -> AlertService:
    return AlertService(
        dismissals=AlertDismissalRepository(session=session),
        settings=AlertSettingRepository(session=session),
        documents=documents,
        ledger=ledger,
    )


AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]


async def get_owned_dismissal(
    dismissal_id: UUID, user: CurrentUserDep, service: AlertServiceDep
) -> AlertDismissal:
    return await service.get_dismissal(dismissal_id=dismissal_id, owner_id=user.id)


OwnedDismissalDep = Annotated[AlertDismissal, Depends(get_owned_dismissal)]
