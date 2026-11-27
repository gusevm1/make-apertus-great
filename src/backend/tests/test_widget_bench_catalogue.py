import json
from typing import Any

import httpx2

from app.clients.apertus import ApertusClient
from app.core.config import get_settings
from app.features.widgets.catalogue.schemas import Kpi, WidgetSpec
from evals.widgets.run import Bench, Run, catalogue_markdown
from tests.conftest import FAKE_USAGE

DATA = {
    "liquidity": {
        "total_chf": 58699.68,
        "accounts": [{"name": "Privatkonto", "balance_chf": 9716.33}],
    }
}
GOOD = WidgetSpec(title="Liquidity", body=Kpi(type="kpi", label="Total", value="total_chf"))
BAD = WidgetSpec(title="Liquidity", body=Kpi(type="kpi", label="Total", value="missing_chf"))


def bench(answers: list[WidgetSpec], requests: list[dict[str, Any]], status: int = 200) -> Bench:
    """A bench whose Apertus answers with the given specs in order, faked at the HTTP level."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        if status != 200:
            return httpx2.Response(status, json={"error": {"message": "fake gateway failure"}})
        message = {"role": "assistant", "content": answers.pop(0).model_dump_json()}
        choice = {"index": 0, "finish_reason": "stop", "message": message}
        return httpx2.Response(200, json={"choices": [choice], "usage": FAKE_USAGE})

    fake_http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    settings = get_settings().model_copy(update={"apertus_max_retries": 0})
    client = ApertusClient(settings=settings, http_client=fake_http)
    return Bench(apertus=client, apertus_schema=client, data=DATA, d3=None, parallel=1)


async def test_a_gateway_failure_is_not_counted_as_the_models() -> None:
    run = Run(variant="catalogue", model="fast", task="liquidity")
    _, tokens_out = await bench(answers=[], requests=[], status=502)._catalogue(
        run=run, messages=[]
    )
    assert run.outcome == "gateway_error"
    assert tokens_out is None
    assert not run.is_clean


def test_the_summary_leaves_gateway_errors_out_of_counts_and_median() -> None:
    runs = [
        Run(variant="catalogue", model="fast", task="a", outcome="first", seconds=2.0),
        Run(variant="catalogue", model="fast", task="b", outcome="repaired", seconds=4.0),
        Run(variant="catalogue", model="fast", task="c", outcome="fallback", seconds=6.0),
        Run(variant="catalogue", model="fast", task="d", outcome="gateway_error", seconds=361.0),
    ]
    row = catalogue_markdown(runs=runs, schema_note="").splitlines()[-1]
    assert row.startswith("| catalogue | fast | 1 of 3 | 1 | 1 | 1 | 0 | 4.0 | 0 of 3 (0%) |")


async def test_a_spec_that_draws_counts_as_first_try() -> None:
    run = Run(variant="catalogue", model="fast", task="liquidity")
    code, _ = await bench(answers=[GOOD], requests=[])._catalogue(run=run, messages=[])
    assert run.outcome == "first"
    assert WidgetSpec.model_validate_json(code) == GOOD


async def test_an_unresolved_path_goes_back_once_with_its_error() -> None:
    requests: list[dict[str, Any]] = []
    run = Run(variant="catalogue", model="fast", task="liquidity")
    code, _ = await bench(answers=[BAD, GOOD], requests=requests)._catalogue(run=run, messages=[])
    assert run.outcome == "repaired"
    assert WidgetSpec.model_validate_json(code) == GOOD
    assert len(requests) == 2
    assert "missing_chf" in json.dumps(requests[1]["messages"][-2:])


async def test_a_second_bad_spec_falls_back_to_data() -> None:
    run = Run(variant="catalogue", model="fast", task="liquidity")
    code, _ = await bench(answers=[BAD, BAD], requests=[])._catalogue(run=run, messages=[])
    assert run.outcome == "fallback"
    assert run.last_error is not None
    assert "missing_chf" in run.last_error
    assert WidgetSpec.model_validate_json(code).body.type == "table"
    assert not run.is_clean
