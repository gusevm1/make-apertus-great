from datetime import date
from typing import Any

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.ledger.schemas import (
    BalanceChange,
    BalanceChangeArgs,
    ComparePeriodsArgs,
    CounterpartySums,
    Filters,
    ForecastMonthsArgs,
    GroupSums,
    MonthSums,
    MonthTrend,
    MovementSearch,
    PeriodComparison,
    SearchMovementsArgs,
    SumByCounterpartyArgs,
    SumByGroupArgs,
    SumByMonthArgs,
    TaxYearArgs,
    TaxYearSummary,
    UnusualMovements,
)
from app.features.ledger.service import LedgerService

PROMPTS = load_prompts(prompts_py=__file__)


def get_tools(service: LedgerService, token: str, today: date) -> list[Tool[Any]]:
    async def search_movements(args: SearchMovementsArgs) -> MovementSearch:
        return await service.search_movements(token=token, args=args)

    async def sum_by_month(args: SumByMonthArgs) -> MonthSums:
        return await service.sum_by_month(token=token, filters=args, today=today)

    async def sum_by_counterparty(args: SumByCounterpartyArgs) -> CounterpartySums:
        return await service.sum_by_counterparty(token=token, args=args)

    async def forecast_months(args: ForecastMonthsArgs) -> MonthTrend:
        return await service.forecast_months(token=token, args=args, today=today)

    async def sum_by_group(args: SumByGroupArgs) -> GroupSums:
        return await service.sum_by_group(token=token, args=args)

    async def find_unusual_movements(args: Filters) -> UnusualMovements:
        return await service.find_unusual_movements(token=token, filters=args, today=today)

    async def compare_periods(args: ComparePeriodsArgs) -> PeriodComparison:
        return await service.compare_periods(token=token, args=args, today=today)

    async def explain_balance_change(args: BalanceChangeArgs) -> BalanceChange:
        return await service.explain_balance_change(token=token, args=args)

    async def tax_year_summary(args: TaxYearArgs) -> TaxYearSummary:
        return await service.tax_year_summary(token=token, args=args, today=today)

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
            args_schema=SumByMonthArgs,
            handler=sum_by_month,
        ),
        Tool(
            name="compare_periods",
            title="Compare two periods",
            icon="git-compare",
            description=PROMPTS["compare_periods"],
            args_schema=ComparePeriodsArgs,
            handler=compare_periods,
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
        Tool(
            name="explain_balance_change",
            title="Explain a balance change",
            icon="scale",
            description=PROMPTS["explain_balance_change"],
            args_schema=BalanceChangeArgs,
            handler=explain_balance_change,
        ),
        Tool(
            name="tax_year_summary",
            title="Gather your tax figures",
            icon="receipt",
            description=PROMPTS["tax_year_summary"],
            args_schema=TaxYearArgs,
            handler=tax_year_summary,
        ),
    ]
