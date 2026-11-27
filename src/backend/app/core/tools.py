from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel


@dataclass(frozen=True)
class TurnResult:
    tool_call_id: UUID
    tool_name: str
    result: dict[str, Any]


@dataclass(frozen=True)
class Turn:
    conversation_id: UUID
    # The turn's earlier calls that returned a result, oldest first.
    results: list[TurnResult]


@dataclass(frozen=True)
class Tool[ArgsT: BaseModel]:
    name: str
    # What a person reads while the tool runs, such as "Search the web".
    title: str
    # A lucide icon name in kebab case, such as "globe".
    icon: str
    description: str
    args_schema: type[ArgsT]
    handler: Callable[[ArgsT], Awaitable[BaseModel]] | None = None
    # For a tool that builds on the turn's earlier results instead of on its arguments alone.
    turn_handler: Callable[[ArgsT, Turn], Awaitable[BaseModel]] | None = None
    # What the customer reads before allowing a call in the page; None: it runs without asking.
    confirmation: str | None = None

    def __post_init__(self) -> None:
        if (self.handler is None) == (self.turn_handler is None):
            raise ValueError(f"Tool {self.name} needs exactly one of handler and turn_handler")
