from typing import Annotated

from fastapi import Depends

from app.clients.banking import BankingClientDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.payments.service import PaymentService


def get_payment_service(banking: BankingClientDep, ledger: LedgerServiceDep) -> PaymentService:
    return PaymentService(banking=banking, ledger=ledger)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]
