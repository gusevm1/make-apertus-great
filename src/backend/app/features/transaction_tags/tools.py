from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.figure_checks.service import FigureCheckService
from app.features.transaction_tags.schemas import SpendingSums, SumSpendingArgs
from app.features.transaction_tags.spending_service import SpendingService

PROMPTS = load_prompts(prompts_py=__file__)
# Above this share of uncertain bookings, a figure gets a pointer to the category center.
UNCERTAIN_SHARE = Decimal("0.1")


def get_tools(
    service: SpendingService, figure_checks: FigureCheckService, owner_id: UUID, token: str
) -> list[Tool[Any]]:
    async def sum_spending(args: SumSpendingArgs) -> SpendingSums:
        return await service.sum_spending(owner_id=owner_id, token=token, args=args)

    def uncertain_pointer(result: dict[str, Any], answer: str) -> str | None:
        sums = SpendingSums.model_validate(result)
        figures = [sums, *sums.groups]
        used = [
            figure
            for figure in figures
            if figure.count > 0
            and Decimal(figure.uncertain_count) / figure.count > UNCERTAIN_SHARE
            and figure_checks.has_figure(answer=answer, value=figure.spent_chf)
        ]
        if not used:
            return None
        # The total holds every group, so a group next to it adds no bookings.
        count = (
            sums.uncertain_count if sums in used else sum(figure.uncertain_count for figure in used)
        )
        return PROMPTS[f"uncertain_pointer_{sums.language}"].format(count=count)

    return [
        Tool(
            name="sum_spending",
            title="Add up your spending",
            icon="pie-chart",
            description=PROMPTS["sum_spending"],
            args_schema=SumSpendingArgs,
            handler=sum_spending,
            pointer=uncertain_pointer,
        )
    ]
