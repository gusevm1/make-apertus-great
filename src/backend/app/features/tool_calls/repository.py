from app.core.repository import BaseRepository
from app.features.tool_calls.models import ToolCallORM
from app.features.tool_calls.schemas import ToolCall


class ToolCallRepository(BaseRepository[ToolCallORM, ToolCall]):
    orm_model = ToolCallORM
    schema = ToolCall
    default_sort = "created_at"
