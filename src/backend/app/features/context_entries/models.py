from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ContextEntryORM(Base):
    __tablename__ = "context_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('goal', 'fact', 'preference')", name="kind"),
        CheckConstraint("status IN ('proposed', 'active', 'dismissed', 'replaced')", name="status"),
        CheckConstraint("source IN ('customer', 'chat')", name="source"),
    )

    owner_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[str]
    status: Mapped[str]
    text: Mapped[str]
    amount_chf: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    target_date: Mapped[date | None]
    source: Mapped[str]
    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("tool_calls.id", ondelete="SET NULL"))
    # Deleting an entry deletes, through this cascade, every earlier version of it.
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("context_entries.id", ondelete="CASCADE"), index=True
    )
    replaces_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("context_entries.id", ondelete="SET NULL")
    )
