from datetime import date
from typing import Annotated, Any

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.clients.searxng import SearxngClientDep
from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.core.tools import Tool
from app.features.accounts import tools as account_tools
from app.features.accounts.dependencies import AccountServiceDep
from app.features.bank_data import tools as bank_data_tools
from app.features.bank_data.dependencies import BankDataServiceDep
from app.features.documents import tools as document_tools
from app.features.documents.dependencies import DocumentServiceDep
from app.features.ledger import tools as ledger_tools
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.service import ToolCallService
from app.features.web_search import tools as web_search_tools
from app.features.web_search.service import WebSearchService

# One for the whole app: the stream that waits and the request that answers share it.
CONFIRMATIONS = Confirmations()


def get_tool_call_repo(session: SessionDep) -> ToolCallRepository:
    return ToolCallRepository(session=session)


async def get_today(ledger: LedgerServiceDep) -> date:
    # ponytail: asked once per turn; cache it when the banking API gets slow
    return await ledger.get_today()


def get_tools(
    searxng: SearxngClientDep,
    user: CurrentUserDep,
    accounts: AccountServiceDep,
    bank_data: BankDataServiceDep,
    documents: DocumentServiceDep,
    ledger: LedgerServiceDep,
    today: Annotated[date, Depends(get_today)],
) -> list[Tool[Any]]:
    # A feature whose tools read the customer's bank data adds its service dependency here.
    return [
        *account_tools.get_tools(service=accounts, token=user.token),
        *bank_data_tools.get_tools(service=bank_data, token=user.token),
        *document_tools.get_tools(service=documents, owner_id=user.id),
        *ledger_tools.get_tools(service=ledger, token=user.token, today=today),
        # Web search sends the query outside the bank, so it needs SearXNG's address to exist.
        *(
            []
            if searxng is None
            else web_search_tools.get_tools(service=WebSearchService(searxng=searxng))
        ),
    ]


def get_tool_call_service(
    tool_calls: Annotated[ToolCallRepository, Depends(get_tool_call_repo)],
    apertus: ApertusClientDep,
    tools: Annotated[list[Tool[Any]], Depends(get_tools)],
    today: Annotated[date, Depends(get_today)],
) -> ToolCallService:
    return ToolCallService(
        tool_calls=tool_calls,
        apertus=apertus,
        tools=tools,
        today=today,
        confirmations=CONFIRMATIONS,
    )


ToolCallServiceDep = Annotated[ToolCallService, Depends(get_tool_call_service)]
