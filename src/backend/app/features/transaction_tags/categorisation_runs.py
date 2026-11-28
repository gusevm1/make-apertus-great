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
    CustomCategoryRepository,
    PersonalTagAssignmentRepository,
    PersonalTagEvaluationRepository,
    PersonalTagRepository,
    SeveritySettingRepository,
    TransactionTagRepository,
)
from app.features.transaction_tags.schemas import CategorisationRun, CategorisationScope
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
# Customers who asked to judge again while a run was going: their run goes on with that.
_redo_after: set[UUID] = set()
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

    async def list_runs(self, owner_id: UUID) -> list[CategorisationRun]:
        """This customer's runs, newest first."""
        return await self.runs.list_for_owner(owner_id=owner_id)

    async def start(
        self, owner_id: UUID, token: str, scope: CategorisationScope = "untagged"
    ) -> tuple[CategorisationRun, bool]:
        """Start a background run, or return the one of this customer that is still going.

        Asked to judge again (`unconfirmed`) while a run is going, that run judges again after it.
        """
        async with _start_lock:
            current = _active.get(owner_id)
            if current is not None and not current.task.done():
                if scope == "unconfirmed":
                    _redo_after.add(owner_id)
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
                    scope=scope,
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
    run_id: UUID,
    owner_id: UUID,
    token: str,
    scope: CategorisationScope,
    ledger: LedgerService,
    apertus: ApertusClient,
) -> None:
    """One run, then one that judges again for each request that came in meanwhile."""
    while True:
        await _work_once(
            run_id=run_id,
            owner_id=owner_id,
            token=token,
            scope=scope,
            ledger=ledger,
            apertus=apertus,
        )
        async with _start_lock:
            if owner_id not in _redo_after:
                return
            _redo_after.discard(owner_id)
            async with session_factory() as session:
                run = await CategorisationRunRepository(session=session).create(owner_id=owner_id)
            run_id, scope = run.id, "unconfirmed"
            _active[owner_id].run_id = run_id


async def _work_once(
    run_id: UUID,
    owner_id: UUID,
    token: str,
    scope: CategorisationScope,
    ledger: LedgerService,
    apertus: ApertusClient,
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
                custom=CustomCategoryRepository(session=session),
                ledger=ledger,
                apertus=apertus,
            ).create_categorisation(owner_id=owner_id, token=token, scope=scope)
            await SeverityService(
                tags=tags,
                severities=SeveritySettingRepository(session=session),
                custom=CustomCategoryRepository(session=session),
                ledger=ledger,
                apertus=apertus,
            ).create_proposal(owner_id=owner_id, token=token)
            evaluations = PersonalTagEvaluationRepository(session=session)
            if scope == "unconfirmed":
                # Every row is judged again, so a tag the customer just added gets its rows.
                await evaluations.delete_for_owner(owner_id=owner_id)
            await PersonalTagService(
                tags=tags,
                personal=PersonalTagRepository(session=session),
                assignments=PersonalTagAssignmentRepository(session=session),
                evaluations=evaluations,
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
