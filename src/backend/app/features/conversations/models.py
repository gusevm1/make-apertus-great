from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ConversationORM(Base):
    __tablename__ = "conversations"

    owner_id: Mapped[UUID] = mapped_column(index=True)
    title: Mapped[str | None]


class MessageORM(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="role"),)

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str]
    content: Mapped[str]
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    quotes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    documents: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
