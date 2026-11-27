from typing import Annotated

from fastapi import Depends

from app.features.bank_data.service import BankDataService
from app.features.ledger.dependencies import LedgerServiceDep


def get_bank_data_service(ledger: LedgerServiceDep) -> BankDataService:
    return BankDataService(ledger=ledger)


BankDataServiceDep = Annotated[BankDataService, Depends(get_bank_data_service)]
