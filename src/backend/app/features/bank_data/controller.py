from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUserDep, require_user
from app.features.bank_data.dependencies import BankDataServiceDep
from app.features.bank_data.schemas import ResponseCustomer, ResponseUpcomingPayments

router = APIRouter(tags=["bank-data"], dependencies=[Depends(require_user)])


@router.get("/customer", response_model=ResponseCustomer)
async def get_customer(user: CurrentUserDep, service: BankDataServiceDep) -> ResponseCustomer:
    """Your name and since when you bank here, as the bank holds them."""
    customer = await service.get_customer(token=user.token)
    return ResponseCustomer.model_validate(customer)


@router.get("/upcoming-payments", response_model=ResponseUpcomingPayments)
async def list_upcoming_payments(
    user: CurrentUserDep,
    service: BankDataServiceDep,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> ResponseUpcomingPayments:
    """List the payments the bank will make, by default in its next 60 days."""
    payments = await service.list_upcoming_payments(
        token=user.token, date_from=date_from, date_to=date_to
    )
    return ResponseUpcomingPayments(root=payments)
