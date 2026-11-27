from typing import Annotated

from fastapi import Depends

from app.features.accounts.service import AccountService
from app.features.ledger.dependencies import LedgerServiceDep


def get_account_service(ledger: LedgerServiceDep) -> AccountService:
    return AccountService(ledger=ledger)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
