from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.budgets.repository import BudgetRepository
from app.features.budgets.schemas import Budget
from app.features.budgets.service import BudgetService
from app.features.transaction_tags.dependencies import SpendingServiceDep


def get_budget_service(session: SessionDep, spending: SpendingServiceDep) -> BudgetService:
    return BudgetService(budgets=BudgetRepository(session=session), spending=spending)


BudgetServiceDep = Annotated[BudgetService, Depends(get_budget_service)]


async def get_owned_budget(
    budget_id: UUID, user: CurrentUserDep, service: BudgetServiceDep
) -> Budget:
    return await service.get_budget(budget_id=budget_id, owner_id=user.id)


OwnedBudgetDep = Annotated[Budget, Depends(get_owned_budget)]
