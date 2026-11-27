from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.recurring_payments.dependencies import RecurringPaymentServiceDep
from app.features.recurring_payments.schemas import ResponseRecurringPayments
from app.features.tool_calls.dependencies import get_today

router = APIRouter(tags=["recurring-payments"], dependencies=[Depends(require_user)])


@router.get("/recurring-payments", response_model=ResponseRecurringPayments)
async def list_recurring_payments(
    user: CurrentUserDep,
    service: RecurringPaymentServiceDep,
    today: Annotated[date, Depends(get_today)],
) -> ResponseRecurringPayments:
    """List the payments that come back every month, quarter or year, and instalment plans."""
    payments = await service.list_recurring(token=user.token, today=today)
    return ResponseRecurringPayments.model_validate(payments, from_attributes=True)
