import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from app.clients.apertus import ApertusClient
from app.core.db import session_factory
from app.core.errors import NotFoundError
from app.features.ledger.service import LedgerService
from app.features.transaction_tags.personal_tag_service import PersonalTagService
from app.features.transaction_tags.repository import (
    CategorisationRunRepository,
    CategoryCorrectionRepository,
    PersonalTagAssignmentRepository,
    PersonalTagEvaluationRepository,
    PersonalTagRepository,
    SeveritySettingRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import CategorisationRun
from app.features.transaction_tags.service import TransactionTagService
from app.features.transaction_tags.severity_service import SeverityService

logger = logging.getLogger(__name__)


@dataclass
class _ActiveRun:
    run_id: UUID
    task: asyncio.Task[None]


# A run blocks the next one only while its task lives in this process (one worker, decision #47).
# The dict also keeps the task referenced, so it isn't garbage-collected mid-run.
_active: dict[UUID, _ActiveRun] = {}
_start_lock = asyncio.Lock()


async def wait_for_runs() -> None:
    """Return once every run started in this process has ended."""
    await asyncio.gather(*(active.task for active in _active.values()), return_exceptions=True)


class CategorisationRunService:
    def __init__(
        self, runs: CategorisationRunRepository, ledger: LedgerService, apertus: ApertusClient
    ) -> None:
        self.runs = runs
        self.ledger = ledger
        self.apertus = apertus

    async def start(self, owner_id: UUID, token: str) -> tuple[CategorisationRun, bool]:
        """Start a background run, or return the one of this customer that is still going."""
        async with _start_lock:
            current = _active.get(owner_id)
            if current is not None and not current.task.done():
                run = await self.get_run(categorisation_id=current.run_id, owner_id=owner_id)
                return run, False
            # Whatever is still queued or running here was lost with an earlier process.
            await self.runs.fail_unfinished(owner_id=owner_id)
            run = await self.runs.create(owner_id=owner_id)
            task = asyncio.create_task(
                _work(
                    run_id=run.id,
                    owner_id=owner_id,
                    token=token,
                    ledger=self.ledger,
                    apertus=self.apertus,
                )
            )
            _active[owner_id] = _ActiveRun(run_id=run.id, task=task)
            task.add_done_callback(lambda _: _forget(owner_id=owner_id, run_id=run.id))
            return run, True

    async def get_run(self, categorisation_id: UUID, owner_id: UUID) -> CategorisationRun:
        run = await self.runs.get_owned(categorisation_id=categorisation_id, owner_id=owner_id)
        if run is None:
            raise NotFoundError(f"No categorisation '{categorisation_id}'")
        return run


def _forget(owner_id: UUID, run_id: UUID) -> None:
    current = _active.get(owner_id)
    if current is not None and current.run_id == run_id:
        del _active[owner_id]


async def _work(
    run_id: UUID, owner_id: UUID, token: str, ledger: LedgerService, apertus: ApertusClient
) -> None:
    """Categories, then severities, then personal tags; each step has its own short sessions."""
    try:
        async with session_factory() as session:
            await CategorisationRunRepository(session=session).mark_running(run_id=run_id)
        async with session_factory() as session:
            tags = TransactionTagRepository(session=session)
            categorisation = await TransactionTagService(
                tags=tags,
                corrections=CategoryCorrectionRepository(session=session),
                ledger=ledger,
                apertus=apertus,
            ).create_categorisation(owner_id=owner_id, token=token)
            await SeverityService(
                tags=tags,
                severities=SeveritySettingRepository(session=session),
                ledger=ledger,
                apertus=apertus,
            ).create_proposal(owner_id=owner_id, token=token)
            await PersonalTagService(
                tags=tags,
                personal=PersonalTagRepository(session=session),
                assignments=PersonalTagAssignmentRepository(session=session),
                evaluations=PersonalTagEvaluationRepository(session=session),
                ledger=ledger,
                apertus=apertus,
            ).create_inference(owner_id=owner_id, token=token)
        status, counts = "done", categorisation.model_dump()
    except Exception:
        logger.exception("Categorisation run %s failed", run_id)
        status, counts = "failed", None
    async with session_factory() as session:
        await CategorisationRunRepository(session=session).mark_finished(
            run_id=run_id, status=status, counts=counts
        )
