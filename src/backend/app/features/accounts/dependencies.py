from typing import Annotated

from fastapi import Depends

from app.clients.banking import BankingClientDep
from app.features.accounts.service import AccountService


def get_account_service(banking: BankingClientDep) -> AccountService:
    return AccountService(banking=banking)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
