from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUserDep, require_user
from app.features.budgets.dependencies import BudgetServiceDep, OwnedBudgetDep
from app.features.budgets.schemas import (
    MONTH_PATTERN,
    Budget,
    RequestBudgetCreate,
    RequestBudgetUpdate,
    ResponseBudget,
    ResponseBudgetSummary,
)
from app.features.tool_calls.dependencies import get_today

router = APIRouter(tags=["budgets"], dependencies=[Depends(require_user)])


def _budget_response(budget: Budget) -> ResponseBudget:
    return ResponseBudget.model_validate(budget, from_attributes=True)


@router.post("/budgets", response_model=ResponseBudget, status_code=201)
async def create_budget(
    body: RequestBudgetCreate, user: CurrentUserDep, service: BudgetServiceDep
) -> ResponseBudget:
    """Set a monthly budget for a spending category."""
    budget = await service.create_budget(data=body, owner_id=user.id)
    return _budget_response(budget=budget)


@router.get("/budgets", response_model=list[ResponseBudget])
async def list_budgets(
    user: CurrentUserDep, service: BudgetServiceDep, sort: str | None = None
) -> list[ResponseBudget]:
    """List your budgets, newest first by default."""
    budgets = await service.list_budgets(owner_id=user.id, sort=sort)
    return [_budget_response(budget=budget) for budget in budgets]


@router.patch("/budgets/{budget_id}", response_model=ResponseBudget)
async def update_budget(
    body: RequestBudgetUpdate, budget: OwnedBudgetDep, service: BudgetServiceDep
) -> ResponseBudget:
    """Change a budget's monthly amount."""
    updated = await service.update_budget(budget=budget, data=body)
    return _budget_response(budget=updated)


@router.delete("/budgets/{budget_id}", status_code=204)
async def delete_budget(budget: OwnedBudgetDep, service: BudgetServiceDep) -> None:
    """Delete a budget."""
    await service.delete_budget(budget_id=budget.id)


@router.get("/budget-summaries", response_model=ResponseBudgetSummary)
async def get_budget_summary(
    user: CurrentUserDep,
    service: BudgetServiceDep,
    today: Annotated[date, Depends(get_today)],
    month: Annotated[str | None, Query(pattern=MONTH_PATTERN)] = None,
) -> ResponseBudgetSummary:
    """Compare your budgets with a month's spending, by default this month's."""
    summary = await service.summarise_month(
        owner_id=user.id, token=user.token, today=today, month=month
    )
    return ResponseBudgetSummary.model_validate(summary, from_attributes=True)
