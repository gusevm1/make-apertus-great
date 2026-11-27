from typing import Annotated

from fastapi import Depends

from app.features.ledger.dependencies import LedgerServiceDep
from app.features.recurring_payments.service import RecurringPaymentService


def get_recurring_payment_service(ledger: LedgerServiceDep) -> RecurringPaymentService:
    return RecurringPaymentService(ledger=ledger)


RecurringPaymentServiceDep = Annotated[
    RecurringPaymentService, Depends(get_recurring_payment_service)
]
