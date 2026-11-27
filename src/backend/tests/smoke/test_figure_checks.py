from typing import Any

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import FakeApertus
from tests.factories import make_conversation
from tests.lookup_tool import LOOKUP
from tests.sse import sse_events


def _lookup(query: str) -> str:
    request = ToolRequest(reason="Needed.", tool=LOOKUP.name, arguments={"query": query})
    return ToolDecision(plan="Look it up.", calls=[request]).model_dump_json()


@pytest.mark.usefixtures("lookup_tool")
async def test_the_stored_and_the_streamed_answer_carry_the_check(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.reply = "You spent CHF 2'916.35, plus CHF 39.90 in fees."

    apertus.decisions = [_lookup(query="2916.35")]
    stored = (await client.post(url, json={"content": "Visa in October?"})).json()
    apertus.decisions = [_lookup(query="2916.35")]
    streamed = await client.post(url, params={"stream": "true"}, json={"content": "Again?"})

    expected = {
        "name": "figures_found",
        "passed": False,
        "detail": "1 of 2 found; not found: 39.90",
    }
    assert stored["provenance"]["checks"][-1] == expected
    name, done = sse_events(response=streamed)[-1]
    assert name == "done"
    assert done["provenance"]["checks"][-1] == expected


@pytest.mark.usefixtures("lookup_tool")
async def test_the_stored_and_the_streamed_answer_carry_the_date_check(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.reply = "December 15: CHF 94.00, Swisscom"

    apertus.decisions = [_lookup(query="Swisscom 2026-12-14 94.00")]
    stored = (await client.post(url, json={"content": "What is due next month?"})).json()
    apertus.decisions = [_lookup(query="Swisscom 2026-12-14 94.00")]
    streamed = await client.post(url, params={"stream": "true"}, json={"content": "Again?"})

    expected = {
        "name": "dates_match",
        "passed": False,
        "detail": "0 of 1 matched; not matched: December 15: CHF 94.00, Swisscom",
    }
    assert stored["provenance"]["checks"][-1] == expected
    name, done = sse_events(response=streamed)[-1]
    assert name == "done"
    assert done["provenance"]["checks"][-1] == expected


INVENTED = "You spent CHF 2'916.35, plus CHF 39.90 in fees."
CORRECTED = "You spent CHF 2'916.35."


def _corrections(apertus: FakeApertus) -> list[str]:
    prompts = [body["messages"][-1]["content"] for body in apertus.requests]
    return [prompt for prompt in prompts if prompt.startswith("Figures not found in the data:")]


def _checks(reply: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["name"]: check for check in reply["provenance"]["checks"]}


@pytest.mark.usefixtures("lookup_tool")
async def test_an_invented_sum_gets_one_corrective_round_and_both_checks_are_stored(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.decisions = [_lookup(query="2916.35")]
    apertus.replies = [INVENTED, CORRECTED]

    reply = (await client.post(url, json={"content": "Visa in October?"})).json()

    (correction,) = _corrections(apertus=apertus)
    assert correction.startswith("Figures not found in the data: 39.90\n")
    assert reply["content"] == CORRECTED
    checks = _checks(reply=reply)
    assert checks["figures_found_draft"] == {
        "name": "figures_found_draft",
        "passed": False,
        "detail": "1 of 2 found; not found: 39.90",
    }
    assert checks["figures_found"] == {
        "name": "figures_found",
        "passed": True,
        "detail": "1 of 1 found",
    }
    stored = (await client.get(url)).json()
    assert stored[-1]["content"] == CORRECTED


@pytest.mark.usefixtures("lookup_tool")
async def test_a_streamed_answer_from_tools_shows_only_its_corrected_text(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.decisions = [_lookup(query="2916.35")]
    apertus.replies = [INVENTED, CORRECTED]

    response = await client.post(url, params={"stream": "true"}, json={"content": "Visa?"})

    events = sse_events(response=response)
    names = [name for name, _ in events]
    assert names[names.index("checking") :] == ["checking", "token", "done"]
    assert [data["text"] for name, data in events if name == "token"] == [CORRECTED]
    done = events[-1][1]
    assert done["content"] == CORRECTED
    assert set(_checks(reply=done)) >= {"figures_found_draft", "figures_found"}


@pytest.mark.usefixtures("lookup_tool")
async def test_an_answer_whose_figures_are_found_gets_no_second_round(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.decisions = [_lookup(query="2916.35")]
    apertus.reply = CORRECTED

    reply = (await client.post(url, json={"content": "Visa in October?"})).json()

    assert _corrections(apertus=apertus) == []
    assert "figures_found_draft" not in _checks(reply=reply)
    assert _checks(reply=reply)["figures_found"]["passed"] is True


async def test_an_answer_without_tool_calls_is_not_corrected(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.reply = INVENTED

    reply = (await client.post(url, json={"content": "Hello"})).json()

    assert _corrections(apertus=apertus) == []
    assert reply["content"] == INVENTED
    assert _checks(reply=reply)["figures_found"]["passed"] is False
