from typing import Annotated

from fastapi import Depends

from app.clients.banking import BankingClientDep
from app.features.ledger.service import LedgerService


def get_ledger_service(banking: BankingClientDep) -> LedgerService:
    return LedgerService(banking=banking)


LedgerServiceDep = Annotated[LedgerService, Depends(get_ledger_service)]
