from typing import Annotated

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.core.auth import CurrentUserDep
from app.features.guardrails.service import GuardrailService
from app.features.ledger.dependencies import LedgerServiceDep


def get_guardrail_service(
    apertus: ApertusClientDep, ledger: LedgerServiceDep, user: CurrentUserDep
) -> GuardrailService:
    return GuardrailService(apertus=apertus, ledger=ledger, token=user.token)


GuardrailServiceDep = Annotated[GuardrailService, Depends(get_guardrail_service)]
