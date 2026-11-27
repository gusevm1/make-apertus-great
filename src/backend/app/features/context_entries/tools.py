from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.context_entries.schemas import ContextEntryList
from app.features.context_entries.service import ContextEntryService

PROMPTS = load_prompts(prompts_py=__file__)
SEARCH_MAX_LENGTH = 200


class ListContextEntriesArgs(BaseModel):
    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=SEARCH_MAX_LENGTH,
        description=PROMPTS["list_context_entries_text"],
    )


def get_tools(service: ContextEntryService, owner_id: UUID) -> list[Tool[Any]]:
    async def list_context_entries(args: ListContextEntriesArgs) -> ContextEntryList:
        listing = await service.list_summaries(owner_id=owner_id, text=args.text)
        if listing.left_out == 0:
            return listing
        note = PROMPTS["list_context_entries_left_out"].format(count=listing.left_out)
        return listing.model_copy(update={"note": note})

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
