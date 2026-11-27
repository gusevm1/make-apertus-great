from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class Tool[ArgsT: BaseModel]:
    name: str
    # What a person reads while the tool runs, such as "Search the web".
    title: str
    # A lucide icon name in kebab case, such as "globe".
    icon: str
    description: str
    args_schema: type[ArgsT]
    handler: Callable[[ArgsT], Awaitable[BaseModel]]
    # What the customer reads before allowing a call in the page; None: it runs without asking.
    confirmation: str | None = None
