from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ToolCallORM(Base):
    __tablename__ = "tool_calls"
    # Also serves lookups by message_id, so that FK needs no index of its own.
    __table_args__ = (UniqueConstraint("message_id", "position"),)

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    position: Mapped[int]
    round: Mapped[int] = mapped_column(server_default="0")
    plan: Mapped[str] = mapped_column(server_default="")
    reason: Mapped[str]
    tool_name: Mapped[str]
    title: Mapped[str] = mapped_column(server_default="")
    icon: Mapped[str] = mapped_column(server_default="")
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    error: Mapped[str | None]
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
