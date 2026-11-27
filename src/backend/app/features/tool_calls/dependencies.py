from datetime import date
from typing import Annotated, Any

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.clients.banking import BankingClientDep
from app.clients.tavily import TavilyClientDep
from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.core.tools import Tool
from app.features.accounts import tools as account_tools
from app.features.accounts.dependencies import AccountServiceDep
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.service import ToolCallService
from app.features.web_search import tools as web_search_tools
from app.features.web_search.service import WebSearchService


def get_tool_call_repo(session: SessionDep) -> ToolCallRepository:
    return ToolCallRepository(session=session)


def get_tools(
    tavily: TavilyClientDep, user: CurrentUserDep, accounts: AccountServiceDep
) -> list[Tool[Any]]:
    # A feature whose tools read the customer's bank data adds its service dependency here.
    return [
        *account_tools.get_tools(service=accounts, token=user.token),
        # Web search sends the question outside the bank, so it only exists when a key is set.
        *(
            []
            if tavily is None
            else web_search_tools.get_tools(service=WebSearchService(tavily=tavily))
        ),
    ]


async def get_today(banking: BankingClientDep) -> date:
    # ponytail: asked once per turn; cache it when the banking API gets slow
    info = await banking.get(path="/system/info")
    return date.fromisoformat(info["today"])


def get_tool_call_service(
    tool_calls: Annotated[ToolCallRepository, Depends(get_tool_call_repo)],
    apertus: ApertusClientDep,
    tools: Annotated[list[Tool[Any]], Depends(get_tools)],
    today: Annotated[date, Depends(get_today)],
) -> ToolCallService:
    return ToolCallService(tool_calls=tool_calls, apertus=apertus, tools=tools, today=today)


ToolCallServiceDep = Annotated[ToolCallService, Depends(get_tool_call_service)]
