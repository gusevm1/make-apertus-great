from typing import Any

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.ledger.schemas import (
    CounterpartySums,
    Filters,
    MonthSums,
    MovementSearch,
    SearchMovementsArgs,
    SumByCounterpartyArgs,
)
from app.features.ledger.service import LedgerService

PROMPTS = load_prompts(prompts_py=__file__)


def get_tools(service: LedgerService, token: str) -> list[Tool[Any]]:
    async def search_movements(args: SearchMovementsArgs) -> MovementSearch:
        return await service.search_movements(token=token, args=args)

    async def sum_by_month(args: Filters) -> MonthSums:
        return await service.sum_by_month(token=token, filters=args)

    async def sum_by_counterparty(args: SumByCounterpartyArgs) -> CounterpartySums:
        return await service.sum_by_counterparty(token=token, args=args)

    return [
        Tool(
            name="search_movements",
            title="Search your bookings",
            icon="list",
            description=PROMPTS["search_movements"],
            args_schema=SearchMovementsArgs,
            handler=search_movements,
        ),
        Tool(
            name="sum_by_month",
            title="Add up your months",
            icon="bar-chart-3",
            description=PROMPTS["sum_by_month"],
            args_schema=Filters,
            handler=sum_by_month,
        ),
        Tool(
            name="sum_by_counterparty",
            title="See where your money goes",
            icon="users",
            description=PROMPTS["sum_by_counterparty"],
            args_schema=SumByCounterpartyArgs,
            handler=sum_by_counterparty,
        ),
    ]
