from typing import Any

from pydantic import BaseModel

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.accounts.schemas import AccountBalances
from app.features.accounts.service import AccountService

PROMPTS = load_prompts(prompts_py=__file__)


class ListAccountsArgs(BaseModel):
    pass


def get_tools(service: AccountService, token: str) -> list[Tool[Any]]:
    async def list_accounts(_: ListAccountsArgs) -> AccountBalances:
        return await service.list_balances(token=token)

    return [
        Tool(
            name="list_accounts",
            title="Check your accounts",
            icon="wallet",
            description=PROMPTS["list_accounts"],
            args_schema=ListAccountsArgs,
            handler=list_accounts,
        )
    ]
