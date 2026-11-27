import builtins
from typing import Any
from uuid import UUID

from app.core.repository import BaseRepository
from app.features.tool_calls.models import ToolCallORM
from app.features.tool_calls.schemas import ToolCall


class ToolCallRepository(BaseRepository[ToolCallORM, ToolCall]):
    orm_model = ToolCallORM
    schema = ToolCall
    default_sort = "created_at"

    async def list(self, *, sort: str | None = None, **filters: Any) -> builtins.list[ToolCall]:
        calls = await super().list(sort=sort, **filters)
        # The figure correction calls Apertus next, which no open transaction may span.
        await self.session.commit()
        return calls

    async def set_outcome(
        self, call_id: UUID, result: dict[str, Any] | None, error: str | None
    ) -> ToolCall:
        row = await self.session.get_one(ToolCallORM, call_id)
        row.result, row.error = result, error
        await self.session.commit()
        return self._to_schema(row=row)
