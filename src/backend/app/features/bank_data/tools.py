from dataclasses import dataclass
from string import Formatter
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.bank_data.schemas import (
    BalancePreviewArgs,
    BankData,
    BookingsArgs,
    CardArgs,
    CardTransactionsArgs,
    FxRatesArgs,
    LoanTransactionsArgs,
    NoArgs,
    PayeesArgs,
    PaymentsArgs,
    PortfolioPerformanceArgs,
    PortfolioTransactionsArgs,
    StandingOrdersArgs,
    UpcomingPaymentsArgs,
)
from app.features.bank_data.service import BankDataService

PROMPTS = load_prompts(prompts_py=__file__)


@dataclass(frozen=True)
class Read:
    """One read endpoint of the banking API as a tool; `{fields}` in the path are arguments."""

    name: str
    title: str
    icon: str
    path: str
    args: type[BaseModel] = NoArgs


# Reads only. Anything that changes the bank (payments, standing orders, widgets) needs the
# customer's confirmation in the page first, and /admin/reset is never a tool.
# A new path also goes into the ledger's READ_PATHS, which is what may be read.
READS = [
    Read(name="get_customer", title="Look at your profile", icon="user", path="/customer"),
    Read(
        name="get_asset_overview",
        title="Add up your assets",
        icon="landmark",
        path="/asset-overview",
    ),
    Read(
        name="get_balance_preview",
        title="Preview your balance",
        icon="trending-up",
        path="/accounts/{account_id}/balance-preview",
        args=BalancePreviewArgs,
    ),
    Read(
        name="list_bookings",
        title="Search your bookings",
        icon="list",
        path="/bookings",
        args=BookingsArgs,
    ),
    Read(
        name="list_payments",
        title="Look at your payments",
        icon="send",
        path="/payments",
        args=PaymentsArgs,
    ),
    Read(
        name="list_upcoming_payments",
        title="Check what is due",
        icon="calendar-clock",
        path="/upcoming-payments",
        args=UpcomingPaymentsArgs,
    ),
    Read(
        name="list_payees",
        title="Look at your payees",
        icon="users",
        path="/payees",
        args=PayeesArgs,
    ),
    Read(
        name="list_standing_orders",
        title="Look at your standing orders",
        icon="repeat",
        path="/standing-orders",
        args=StandingOrdersArgs,
    ),
    Read(name="list_cards", title="Look at your cards", icon="credit-card", path="/cards"),
    Read(
        name="list_card_statements",
        title="Look at your card statements",
        icon="receipt",
        path="/cards/{card_id}/statements",
        args=CardArgs,
    ),
    Read(
        name="list_card_transactions",
        title="Search your card purchases",
        icon="shopping-bag",
        path="/cards/{card_id}/transactions",
        args=CardTransactionsArgs,
    ),
    Read(name="get_portfolio", title="Look at your portfolio", icon="pie-chart", path="/portfolio"),
    Read(
        name="list_portfolio_positions",
        title="Look at your positions",
        icon="layers",
        path="/portfolio/positions",
    ),
    Read(
        name="get_portfolio_performance",
        title="Check your portfolio's performance",
        icon="line-chart",
        path="/portfolio/performance",
        args=PortfolioPerformanceArgs,
    ),
    Read(
        name="list_portfolio_transactions",
        title="Look at your trades",
        icon="arrow-left-right",
        path="/portfolio/transactions",
        args=PortfolioTransactionsArgs,
    ),
    Read(name="list_loans", title="Look at your loans", icon="home", path="/loans"),
    Read(
        name="list_loan_transactions",
        title="Look at your loan payments",
        icon="percent",
        path="/loan-transactions",
        args=LoanTransactionsArgs,
    ),
    Read(
        name="get_fx_rates",
        title="Look up exchange rates",
        icon="coins",
        path="/fx-rates",
        args=FxRatesArgs,
    ),
]


def get_tools(service: BankDataService, token: str) -> list[Tool[Any]]:
    return [_tool(read=read, service=service, token=token) for read in READS]


def _tool(read: Read, service: BankDataService, token: str) -> Tool[Any]:
    in_path = {field for _, field, _, _ in Formatter().parse(read.path) if field}

    async def handler(args: BaseModel) -> BankData:
        values = args.model_dump(mode="json", by_alias=True, exclude_none=True)
        # Quoted, so an id the model made up cannot reach another path of the banking API.
        path = read.path.format(
            **{field: quote(str(values.pop(field)), safe="") for field in in_path}
        )
        return await service.read(path=path, token=token, params=values)

    return Tool(
        name=read.name,
        title=read.title,
        icon=read.icon,
        description=PROMPTS[read.name],
        args_schema=read.args,
        handler=handler,
    )
