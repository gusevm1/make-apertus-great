from typing import Annotated

from fastapi import Depends

from app.clients.banking import BankingClientDep
from app.features.bank_data.service import BankDataService


def get_bank_data_service(banking: BankingClientDep) -> BankDataService:
    return BankDataService(banking=banking)


BankDataServiceDep = Annotated[BankDataService, Depends(get_bank_data_service)]
