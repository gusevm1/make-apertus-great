from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WidgetORM(Base):
    __tablename__ = "widgets"

    owner_id: Mapped[UUID] = mapped_column(index=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str]
    current_version: Mapped[int]
    # The copy on the e-banking dashboard (#26): where it is and which version it shows.
    dashboard_id: Mapped[str | None]
    dashboard_widget_id: Mapped[str | None]
    published_version: Mapped[int | None]


class WidgetVersionORM(Base):
    __tablename__ = "widget_versions"
    # Also serves lookups by widget_id, so that FK needs no index of its own.
    __table_args__ = (UniqueConstraint("widget_id", "number"),)

    widget_id: Mapped[UUID] = mapped_column(ForeignKey("widgets.id", ondelete="CASCADE"))
    number: Mapped[int]
    # The catalogue spec and the DATA it draws; the page is rendered from them on every read.
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    request: Mapped[str]
    model: Mapped[str | None]
    latency_ms: Mapped[int]
    tool_call_ids: Mapped[list[str]] = mapped_column(JSONB)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
