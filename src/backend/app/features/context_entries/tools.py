from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.context_entries.schemas import ContextEntryList
from app.features.context_entries.service import ContextEntryService

PROMPTS = load_prompts(prompts_py=__file__)


class ListContextEntriesArgs(BaseModel):
    pass


def get_tools(service: ContextEntryService, owner_id: UUID) -> list[Tool[Any]]:
    async def list_context_entries(_: ListContextEntriesArgs) -> ContextEntryList:
        return ContextEntryList(entries=await service.list_entries(owner_id=owner_id))

    return [
        Tool(
            name="list_context_entries",
            title="Look at your notes",
            icon="notebook-pen",
            description=PROMPTS["list_context_entries"],
            args_schema=ListContextEntriesArgs,
            handler=list_context_entries,
        )
    ]
