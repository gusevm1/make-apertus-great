from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select, update

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

    # With words, only the entries holding one, those holding the most first; then newest first.
    async def list_active(self, owner_id: UUID, words: list[str]) -> list[ContextEntry]:
        stmt = select(ContextEntryORM).where(
            ContextEntryORM.owner_id == owner_id, ContextEntryORM.status == "active"
        )
        if words:
            matches = [ContextEntryORM.text.icontains(word, autoescape=True) for word in words]
            first, *rest = [case((match, 1), else_=0) for match in matches]
            hits = sum(rest, first)
            stmt = stmt.where(or_(*matches)).order_by(hits.desc())
        rows = await self.session.scalars(stmt.order_by(ContextEntryORM.created_at.desc()))
        return [self._to_schema(row=row) for row in rows]

    async def count_active(self, owner_id: UUID) -> int:
        stmt = select(func.count()).where(
            ContextEntryORM.owner_id == owner_id, ContextEntryORM.status == "active"
        )
        return await self.session.scalar(stmt) or 0

    async def replace(self, entry_id: UUID, fields: dict[str, Any]) -> ContextEntry | None:
        new = ContextEntryORM(**fields)
        self.session.add(new)
        await self.session.flush()
        # The status check sits in the UPDATE, so of two parallel changes only one wins.
        stmt = (
            update(ContextEntryORM)
            .where(ContextEntryORM.id == entry_id, ContextEntryORM.status == "active")
            .values(status="replaced", replaced_by_id=new.id)
            .returning(ContextEntryORM.id)
        )
        if await self.session.scalar(stmt) is None:
            await self.session.rollback()
            return None
        await self.session.commit()
        return self._to_schema(row=new)
