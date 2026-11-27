import json
from typing import Any

import httpx2

from app.clients.apertus import ApertusClient
from app.core.config import get_settings
from app.features.widgets.catalogue.schemas import Kpi, WidgetSpec
from evals.widgets.run import Bench, Run
from tests.conftest import FAKE_USAGE

DATA = {
    "liquidity": {
        "total_chf": 58699.68,
        "accounts": [{"name": "Privatkonto", "balance_chf": 9716.33}],
    }
}
GOOD = WidgetSpec(title="Liquidity", body=Kpi(type="kpi", label="Total", value="total_chf"))
BAD = WidgetSpec(title="Liquidity", body=Kpi(type="kpi", label="Total", value="missing_chf"))


def bench(answers: list[WidgetSpec], requests: list[dict[str, Any]]) -> Bench:
    """A bench whose Apertus answers with the given specs in order, faked at the HTTP level."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        message = {"role": "assistant", "content": answers.pop(0).model_dump_json()}
        choice = {"index": 0, "finish_reason": "stop", "message": message}
        return httpx2.Response(200, json={"choices": [choice], "usage": FAKE_USAGE})

    fake_http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    client = ApertusClient(settings=get_settings(), http_client=fake_http)
    return Bench(apertus=client, apertus_schema=client, data=DATA, d3=None, parallel=1)


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
