from datetime import date
from typing import Any
from uuid import UUID

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.budgets.schemas import BudgetSummary, CompareBudgetsArgs
from app.features.budgets.service import BudgetService

PROMPTS = load_prompts(prompts_py=__file__)


def get_tools(service: BudgetService, owner_id: UUID, token: str, today: date) -> list[Tool[Any]]:
    async def compare_budgets(args: CompareBudgetsArgs) -> BudgetSummary:
        return await service.summarise_month(
            owner_id=owner_id, token=token, today=today, month=args.month
        )

    return [
        Tool(
            name="compare_budgets",
            title="Compare with your budgets",
            icon="wallet",
            description=PROMPTS["compare_budgets"],
            args_schema=CompareBudgetsArgs,
            handler=compare_budgets,
        )
    ]
