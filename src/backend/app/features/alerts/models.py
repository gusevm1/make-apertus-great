from uuid import UUID

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AlertDismissalORM(Base):
    __tablename__ = "alert_dismissals"
    __table_args__ = (UniqueConstraint("owner_id", "key"),)

    owner_id: Mapped[UUID] = mapped_column(index=True)
    key: Mapped[str] = mapped_column(String(200))


class AlertSettingORM(Base):
    __tablename__ = "alert_settings"
    __table_args__ = (
        UniqueConstraint("owner_id", "kind"),
        CheckConstraint("kind IN ('invoice')", name="kind"),
    )

    owner_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[str]
    enabled: Mapped[bool]
