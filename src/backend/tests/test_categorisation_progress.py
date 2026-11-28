from datetime import UTC, datetime
from uuid import uuid4

import httpx2
import pytest

from app.features.transaction_tags.categorisation_runs import wait_for_runs
from app.features.transaction_tags.repository import CategorisationRunRepository
from app.features.transaction_tags.schemas import CategorisationRun
from app.main import app
from tests.conftest import FakeApertus
from tests.test_transaction_tags import LUKAS_BOOKINGS, _bank_client, _by_keyword


@pytest.fixture
async def lukas(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(
        bookings_by_token={"customer-token": ("CUST-001", LUKAS_BOOKINGS)}
    )
    apertus.structured_reply = _by_keyword
    return client


def _run(status: str, step: str, done: int, total: int) -> CategorisationRun:
    return CategorisationRun(
        id=uuid4(),
        owner_id=uuid4(),
        status=status,  # type: ignore[arg-type]
        step=step,  # type: ignore[arg-type]
        step_done=done,
        step_total=total,
        tagged_by_rule=0,
        tagged_by_correction=0,
        tagged_by_model=0,
        already_tagged=0,
        skipped=0,
        created_at=datetime.now(tz=UTC),
        started_at=None,
        finished_at=None,
    )


def test_progress_runs_through_the_steps_from_0_to_100() -> None:
    assert _run(status="queued", step="categories", done=0, total=0).progress == 0
    assert _run(status="running", step="categories", done=50, total=100).progress == 42
    assert _run(status="running", step="necessity", done=0, total=1).progress == 85
    assert _run(status="running", step="personal_tags", done=1, total=2).progress == 95
    assert _run(status="done", step="personal_tags", done=1, total=2).progress == 100


async def test_a_run_reports_each_step_as_it_goes(
    lukas: httpx2.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reported: list[tuple[str, int, int]] = []
    original = CategorisationRunRepository.mark_progress

    async def record(
        self: CategorisationRunRepository, run_id: object, step: str, done: int, total: int
    ) -> None:
        reported.append((step, done, total))
        await original(self, run_id=run_id, step=step, done=done, total=total)  # type: ignore[arg-type]

    monkeypatch.setattr(CategorisationRunRepository, "mark_progress", record)

    started = await lukas.post("/api/categorisations")
    await wait_for_runs()
    run = (await lukas.get(f"/api/categorisations/{started.json()['id']}")).json()

    assert started.json()["progress"] == 0
    categories = [entry for entry in reported if entry[0] == "categories"]
    # One booking is a loan, set by rule before Apertus; then the batch of the other four.
    assert categories == [("categories", 1, 5), ("categories", 5, 5)]
    assert ("necessity", 0, 1) in reported
    assert run["status"] == "done"
    assert run["progress"] == 100
