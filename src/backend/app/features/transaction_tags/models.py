from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TransactionTagORM(Base):
    __tablename__ = "transaction_tags"
    __table_args__ = (
        UniqueConstraint("owner_id", "row_source", "row_id"),
        CheckConstraint("row_source IN ('booking', 'card_transaction')", name="row_source"),
        CheckConstraint("category_set_by IN ('rule', 'model', 'customer')", name="set_by"),
    )

    owner_id: Mapped[UUID]
    row_source: Mapped[str]
    row_id: Mapped[str]
    category: Mapped[str]
    category_set_by: Mapped[str]
    category_model: Mapped[str | None]
    category_confirmed: Mapped[bool] = mapped_column(server_default="false")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
