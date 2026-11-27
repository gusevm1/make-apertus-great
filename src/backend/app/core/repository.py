import builtins
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base
from app.core.errors import BadRequestError


class BaseRepository[ORMT: Base, SchemaT: BaseModel]:
    orm_model: ClassVar[type[Base]]
    schema: ClassVar[type[BaseModel]]
    sortable_fields: ClassVar[frozenset[str]] = frozenset({"created_at"})
    default_sort: ClassVar[str] = "-created_at"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> SchemaT | None:
        row = await self.session.get(self.orm_model, entity_id)
        return self._to_schema(row=row) if row is not None else None

    async def list(self, *, sort: str | None = None, **filters: Any) -> builtins.list[SchemaT]:
        stmt = (
            select(self.orm_model)
            .filter_by(**filters)
            .order_by(self._order_by(sort=sort or self.default_sort))
        )
        rows = await self.session.scalars(stmt)
        return [self._to_schema(row=row) for row in rows]

    async def create(self, data: BaseModel | None = None, **extra: Any) -> SchemaT:
        row = self.orm_model(**(data.model_dump() if data is not None else {}), **extra)
        self.session.add(row)
        # No refresh: the INSERT returned the defaults, and a SELECT would reopen a transaction.
        await self.session.commit()
        return self._to_schema(row=row)

    async def update(self, entity_id: UUID, data: BaseModel) -> SchemaT | None:
        row = await self.session.get(self.orm_model, entity_id)
        if row is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await self.session.commit()
        return self._to_schema(row=row)

    async def delete(self, entity_id: UUID) -> bool:
        row = await self.session.get(self.orm_model, entity_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.commit()
        return True

    def _order_by(self, sort: str) -> UnaryExpression[Any]:
        field = sort.removeprefix("-")
        if field not in self.sortable_fields:
            allowed = ", ".join(sorted(self.sortable_fields))
            raise BadRequestError(f"Cannot sort by '{field}'. Allowed: {allowed}")
        column = getattr(self.orm_model, field)
        return column.desc() if sort.startswith("-") else column.asc()

    def _to_schema(self, row: Base) -> SchemaT:
        return self.schema.model_validate(row, from_attributes=True)  # pyright: ignore[reportReturnType]
