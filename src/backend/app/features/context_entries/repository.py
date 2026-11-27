from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.core.repository import BaseRepository
from app.features.context_entries.models import ContextEntryORM
from app.features.context_entries.schemas import ContextEntry


class ContextEntryRepository(BaseRepository[ContextEntryORM, ContextEntry]):
    orm_model = ContextEntryORM
    schema = ContextEntry

    async def get_owned(self, entry_id: UUID, owner_id: UUID) -> ContextEntry | None:
        stmt = select(ContextEntryORM).filter_by(id=entry_id, owner_id=owner_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None

    async def count_active(self, owner_id: UUID) -> int:
        stmt = select(func.count()).where(
            ContextEntryORM.owner_id == owner_id, ContextEntryORM.status == "active"
        )
        return await self.session.scalar(stmt) or 0

    async def replace(self, entry_id: UUID, fields: dict[str, Any]) -> ContextEntry:
        """Store `fields` as a new entry and mark `entry_id` replaced by it, in one commit."""
        old = await self.session.get_one(ContextEntryORM, entry_id)
        new = ContextEntryORM(**fields)
        self.session.add(new)
        await self.session.flush()
        old.status = "replaced"
        old.replaced_by_id = new.id
        await self.session.commit()
        return self._to_schema(row=new)
