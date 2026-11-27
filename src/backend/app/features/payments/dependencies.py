from typing import Annotated

from fastapi import Depends

from app.clients.banking import BankingClientDep
from app.features.payments.service import PaymentService


def get_payment_service(banking: BankingClientDep) -> PaymentService:
    return PaymentService(banking=banking)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]
