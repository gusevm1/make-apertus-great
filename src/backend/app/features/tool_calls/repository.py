import builtins
from typing import Any

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
