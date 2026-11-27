from datetime import date
from typing import Any

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.ledger.schemas import (
    CounterpartySums,
    Filters,
    ForecastMonthsArgs,
    GroupSums,
    MonthSums,
    MonthTrend,
    MovementSearch,
    SearchMovementsArgs,
    SumByCounterpartyArgs,
    SumByGroupArgs,
    UnusualMovements,
)
from app.features.ledger.service import LedgerService

PROMPTS = load_prompts(prompts_py=__file__)


def get_tools(service: LedgerService, token: str, today: date) -> list[Tool[Any]]:
    async def search_movements(args: SearchMovementsArgs) -> MovementSearch:
        return await service.search_movements(token=token, args=args)

    async def sum_by_month(args: Filters) -> MonthSums:
        return await service.sum_by_month(token=token, filters=args)

    async def sum_by_counterparty(args: SumByCounterpartyArgs) -> CounterpartySums:
        return await service.sum_by_counterparty(token=token, args=args)

    async def forecast_months(args: ForecastMonthsArgs) -> MonthTrend:
        return await service.forecast_months(token=token, args=args, today=today)

    async def sum_by_group(args: SumByGroupArgs) -> GroupSums:
        return await service.sum_by_group(token=token, args=args)

    async def find_unusual_movements(args: Filters) -> UnusualMovements:
        return await service.find_unusual_movements(token=token, filters=args, today=today)

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
        Tool(
            name="forecast_months",
            title="Look at your trend",
            icon="trending-up",
            description=PROMPTS["forecast_months"],
            args_schema=ForecastMonthsArgs,
            handler=forecast_months,
        ),
        Tool(
            name="sum_by_group",
            title="Add up your bookings",
            icon="layers",
            description=PROMPTS["sum_by_group"],
            args_schema=SumByGroupArgs,
            handler=sum_by_group,
        ),
        Tool(
            name="find_unusual_movements",
            title="Look for unusual payments",
            icon="alert-triangle",
            description=PROMPTS["find_unusual_movements"],
            args_schema=Filters,
            handler=find_unusual_movements,
        ),
    ]
