from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BudgetORM(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("owner_id", "category"),
        CheckConstraint("amount_chf > 0 AND amount_chf <= 100000", name="amount_chf"),
    )

    # The unique (owner_id, category) index serves lookups by owner too.
    owner_id: Mapped[UUID]
    category: Mapped[str]
    amount_chf: Mapped[Decimal] = mapped_column(Numeric(12, 2))
