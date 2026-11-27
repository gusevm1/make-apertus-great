import calendar
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.core.errors import ConflictError, NotFoundError
from app.features.budgets.repository import BudgetRepository
from app.features.budgets.schemas import (
    Budget,
    BudgetLine,
    BudgetSummary,
    RequestBudgetCreate,
    RequestBudgetUpdate,
    UnbudgetedSpending,
)
from app.features.transaction_tags.schemas import CATEGORIES, SumSpendingArgs
from app.features.transaction_tags.spending_service import SpendingService


class BudgetService:
    def __init__(self, budgets: BudgetRepository, spending: SpendingService) -> None:
        self.budgets = budgets
        self.spending = spending

    async def create_budget(self, data: RequestBudgetCreate, owner_id: UUID) -> Budget:
        """Store a monthly budget for a category that has none yet."""
        budget = await self.budgets.create_if_new(data=data, owner_id=owner_id)
        if budget is None:
            raise ConflictError(f"You have a budget for {data.category} already, change that one")
        return budget

    async def list_budgets(self, owner_id: UUID, sort: str | None = None) -> list[Budget]:
        """List the customer's budgets."""
        return await self.budgets.list(sort=sort, owner_id=owner_id)

    async def get_budget(self, budget_id: UUID, owner_id: UUID) -> Budget:
        """Return the customer's budget; someone else's counts as not found."""
        budget = await self.budgets.get_owned(budget_id=budget_id, owner_id=owner_id)
        if budget is None:
            raise NotFoundError("Budget not found")
        return budget

    async def update_budget(self, budget: Budget, data: RequestBudgetUpdate) -> Budget:
        """Change a budget's monthly amount."""
        updated = await self.budgets.update(entity_id=budget.id, data=data)
        if updated is None:
            raise NotFoundError("Budget not found")
        return updated

    async def delete_budget(self, budget_id: UUID) -> None:
        """Delete a budget."""
        if not await self.budgets.delete(entity_id=budget_id):
            raise NotFoundError("Budget not found")

    async def summarise_month(
        self, owner_id: UUID, token: str, today: date, month: str | None
    ) -> BudgetSummary:
        """Each budget against the month's spending, and the spending that has no budget."""
        first = today.replace(day=1) if month is None else date.fromisoformat(f"{month}-01")
        days_in_month = calendar.monthrange(first.year, first.month)[1]
        last = first.replace(day=days_in_month)
        sums = await self.spending.sum_spending(
            owner_id=owner_id,
            token=token,
            args=SumSpendingArgs(group_by="category", date_from=first, date_to=last),
        )
        spent = {group.group: group.spent_chf for group in sums.groups}
        budgets = sorted(
            await self.budgets.list_for_owner(owner_id=owner_id),
            key=lambda budget: CATEGORIES.index(budget.category),
        )
        lines = [
            _line(budget=budget, spent_chf=spent.get(budget.category, Decimal(0)))
            for budget in budgets
        ]
        budgeted = {budget.category for budget in budgets}
        budget_chf = sum((line.budget_chf for line in lines), Decimal(0))
        spent_chf = sum((line.spent_chf for line in lines), Decimal(0))
        return BudgetSummary(
            month=f"{first:%Y-%m}",
            days_in_month=days_in_month,
            days_elapsed=_days_elapsed(today=today, first=first, last=last),
            budget_chf=budget_chf,
            spent_chf=spent_chf,
            left_chf=budget_chf - spent_chf,
            over=spent_chf > budget_chf,
            budgets=lines,
            unbudgeted=[
                UnbudgetedSpending(category=group.group, spent_chf=group.spent_chf)
                for group in sums.groups
                if group.group not in budgeted
            ],
            row_ids={category: [] for category in budgeted} | sums.row_ids,
        )


def _line(budget: Budget, spent_chf: Decimal) -> BudgetLine:
    return BudgetLine(
        category=budget.category,
        budget_chf=budget.amount_chf,
        spent_chf=spent_chf,
        left_chf=budget.amount_chf - spent_chf,
        over=spent_chf > budget.amount_chf,
    )


def _days_elapsed(today: date, first: date, last: date) -> int | None:
    if today > last:
        return None
    if today < first:
        return 0
    return today.day
