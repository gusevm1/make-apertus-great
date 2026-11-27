from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.repository import BaseRepository
from app.features.budgets.models import BudgetORM
from app.features.budgets.schemas import Budget, RequestBudgetCreate


class BudgetRepository(BaseRepository[BudgetORM, Budget]):
    orm_model = BudgetORM
    schema = Budget
    sortable_fields = frozenset({"created_at", "category", "amount_chf"})

    async def get_owned(self, budget_id: UUID, owner_id: UUID) -> Budget | None:
        stmt = select(BudgetORM).filter_by(id=budget_id, owner_id=owner_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None

    async def list_for_owner(self, owner_id: UUID) -> list[Budget]:
        budgets = await self.list(owner_id=owner_id)
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return budgets

    async def create_if_new(self, data: RequestBudgetCreate, owner_id: UUID) -> Budget | None:
        """Store the budget, or return None when the category has one already."""
        stmt = (
            insert(BudgetORM)
            .values(owner_id=owner_id, **data.model_dump())
            .on_conflict_do_nothing(index_elements=["owner_id", "category"])
            .returning(BudgetORM)
        )
        row = await self.session.scalar(stmt)
        await self.session.commit()
        return self._to_schema(row=row) if row is not None else None
