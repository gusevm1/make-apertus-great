from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.repository import BaseRepository
from app.features.widgets.models import WidgetORM, WidgetVersionORM
from app.features.widgets.schemas import Widget, WidgetVersion


class WidgetRepository(BaseRepository[WidgetORM, Widget]):
    orm_model = WidgetORM
    schema = Widget

    async def get_owned(self, widget_id: UUID, owner_id: UUID) -> Widget | None:
        stmt = select(WidgetORM).filter_by(id=widget_id, owner_id=owner_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None

    async def create_with_version(
        self, widget: dict[str, Any], version: dict[str, Any]
    ) -> tuple[Widget, WidgetVersion]:
        widget_row = WidgetORM(**widget)
        self.session.add(widget_row)
        await self.session.flush()
        version_row = WidgetVersionORM(widget_id=widget_row.id, **version)
        self.session.add(version_row)
        await self.session.commit()
        return self._to_schema(row=widget_row), WidgetVersion.model_validate(version_row)


class WidgetVersionRepository(BaseRepository[WidgetVersionORM, WidgetVersion]):
    orm_model = WidgetVersionORM
    schema = WidgetVersion

    async def get_number(self, widget_id: UUID, number: int) -> WidgetVersion | None:
        stmt = select(WidgetVersionORM).filter_by(widget_id=widget_id, number=number)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None
