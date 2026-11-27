from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.errors import BadRequestError
from app.core.prompts import load_prompts
from app.core.tools import Tool, Turn
from app.features.context_entries.schemas import (
    AMOUNT_MAX,
    TEXT_MAX_LENGTH,
    ContextEntry,
    ContextEntryList,
    Kind,
    RequestContextEntryCreate,
)
from app.features.context_entries.service import ContextEntryService

PROMPTS = load_prompts(prompts_py=__file__)
SEARCH_MAX_LENGTH = 200
PROPOSE = "propose_context_entry"
ONE_PROPOSAL_PER_TURN = "This message has its proposal already. Propose nothing more."


class ListContextEntriesArgs(BaseModel):
    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=SEARCH_MAX_LENGTH,
        description=PROMPTS["list_context_entries_text"],
    )


class ProposeContextEntryArgs(BaseModel):
    kind: Kind = Field(description=PROMPTS["propose_context_entry_kind"])
    text: str = Field(
        min_length=1, max_length=TEXT_MAX_LENGTH, description=PROMPTS["propose_context_entry_text"]
    )
    amount_chf: Decimal | None = Field(
        default=None,
        ge=0,
        le=AMOUNT_MAX,
        decimal_places=2,
        description=PROMPTS["propose_context_entry_amount"],
    )
    target_date: date | None = Field(
        default=None, description=PROMPTS["propose_context_entry_date"]
    )
    replaces: str | None = Field(
        default=None, min_length=1, description=PROMPTS["propose_context_entry_replaces"]
    )


def get_tools(service: ContextEntryService, owner_id: UUID) -> list[Tool[Any]]:
    async def list_context_entries(args: ListContextEntriesArgs) -> ContextEntryList:
        listing = await service.list_summaries(owner_id=owner_id, text=args.text)
        if listing.left_out == 0:
            return listing
        note = PROMPTS["list_context_entries_left_out"].format(count=listing.left_out)
        return listing.model_copy(update={"note": note})

    async def propose_context_entry(args: ProposeContextEntryArgs, turn: Turn) -> ContextEntry:
        if any(result.tool_name == PROPOSE for result in turn.results):
            raise BadRequestError(ONE_PROPOSAL_PER_TURN)
        return await service.propose_entry(
            data=RequestContextEntryCreate.model_validate(args.model_dump(exclude={"replaces"})),
            replaces=args.replaces,
            owner_id=owner_id,
            tool_call_id=turn.call_id,
        )

    return [
        Tool(
            name="list_context_entries",
            title="Look at your notes",
            icon="notebook-pen",
            description=PROMPTS["list_context_entries"],
            args_schema=ListContextEntriesArgs,
            handler=list_context_entries,
        ),
        Tool(
            name=PROPOSE,
            title="Suggest an entry to remember",
            icon="bookmark-plus",
            description=PROMPTS[PROPOSE],
            args_schema=ProposeContextEntryArgs,
            turn_handler=propose_context_entry,
        ),
    ]
