"""The plan without the model: a client that always fails, against the running banking API.

uv run python -m evals.boards.fallback
"""

import asyncio
import sys
from typing import Any

from app.clients.banking import BankingClient
from app.core.config import Settings
from app.core.errors import UpstreamError
from app.features.board_plans.service import NOT_PICKED, NOT_PLANNED, BoardPlanService
from app.features.figure_checks.service import FigureCheckService
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.service import TileService
from evals.boards.run import CUSTOMERS, REQUESTS, login


class FailingClient:
    """Answers every call the way a gateway that timed out does."""

    async def structured(self, *args: Any, **kwargs: Any) -> Any:
        raise UpstreamError("Apertus timed out")


async def main() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    banking = BankingClient(settings=settings)
    failures = []
    for customer in CUSTOMERS:
        ledger = LedgerService(banking=banking)
        recurring = RecurringPaymentService(ledger=ledger)
        service = BoardPlanService(
            apertus=FailingClient(),  # type: ignore[arg-type]
            tiles=TileService(ledger=ledger, recurring=recurring),
            ledger=ledger,
            recurring=recurring,
            figure_checks=FigureCheckService(),
        )
        token = await login(settings=settings, customer=customer)
        today = await ledger.get_today()
        plan = await service.plan_boards(token=token, today=today)
        check = next(c for c in plan.checks if c.name == "planned_by_model")
        board = plan.boards[0]
        ok = (
            plan.model == "server"
            and not check.passed
            and check.detail == NOT_PLANNED
            and len(board.tiles) >= 5
            and len(plan.ideas) == 3
        )
        print(  # noqa: T201
            f"{customer} first: {'ok' if ok else 'FAIL'}, {board.name}: "
            + ", ".join(f"{t.title} ({t.template})" for t in board.tiles)
            + f"; ideas: {', '.join(i.title for i in plan.ideas)}"
        )
        if not ok:
            failures.append(f"{customer} first")
        for request in REQUESTS[customer]:
            asked = await service.plan_boards(token=token, today=today, request=request)
            check = next(c for c in asked.checks if c.name == "planned_by_model")
            tiles = asked.boards[0].tiles
            # A board, or an empty one that says why: never an error.
            ok = check.detail == NOT_PICKED and (bool(tiles) or bool(asked.dropped))
            print(  # noqa: T201
                f"  {request}: {'ok' if ok else 'FAIL'}, {asked.boards[0].name}: "
                + (", ".join(f"{t.title} ({t.template})" for t in tiles) or "empty")
                + ("" if tiles else f" ({asked.dropped[-1].reason})")
            )
            if not ok:
                failures.append(f"{customer}: {request}")
    await banking.close()
    print("all fell back cleanly" if not failures else f"FAILED: {failures}")  # noqa: T201
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
