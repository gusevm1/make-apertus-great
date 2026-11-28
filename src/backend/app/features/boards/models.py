from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BoardORM(Base):
    __tablename__ = "boards"

    owner_id: Mapped[UUID] = mapped_column(index=True)
    name: Mapped[str]
    position: Mapped[int]
    # The plan this board was built from; None for a board the customer started empty.
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("board_plans.id", ondelete="SET NULL"))


class BoardTileORM(Base):
    __tablename__ = "board_tiles"

    board_id: Mapped[UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    template: Mapped[str]
    args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    title: Mapped[str]
    position: Mapped[int]


class BoardPlanORM(Base):
    __tablename__ = "board_plans"

    owner_id: Mapped[UUID] = mapped_column(index=True)
    request: Mapped[str | None]
    kind: Mapped[str]
    evidence: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    question: Mapped[str]
    ideas: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    dropped: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    model: Mapped[str | None]
    latency_ms: Mapped[int]
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
