import asyncio
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tool_calls import service as tool_call_service
from app.features.tool_calls.dependencies import CONFIRMATIONS
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.features.tool_calls.service import NOT_ALLOWED
from app.main import app
from tests.conftest import FakeApertus, FakeSearxng
from tests.factories import make_conversation
from tests.sse import sse_events

SEARCH_TOOL = "search_web"
CONFIRMATION = "This sends the query to search engines outside the bank."
SNB_PAGE = {
    "title": "Geldpolitische Lagebeurteilung",
    "url": "https://www.snb.ch/de/publications/communication/press-releases",
    "content": "Die SNB belässt den SNB-Leitzins bei 0 %.",
    "score": 0.9,
}


def _search(query: str) -> str:
    request = ToolRequest(reason="Current rate.", tool=SEARCH_TOOL, arguments={"query": query})
    return ToolDecision(plan="Search the web.", calls=[request]).model_dump_json()


async def _stream(client: httpx2.AsyncClient, url: str) -> httpx2.Response:
    return await client.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "SNB-Leitzins?"}
    )


async def _waiting_call() -> tuple[UUID, UUID]:
    """The conversation and id of the one call that waits, as soon as it waits."""
    # The test transport hands a stream over once it has ended, so no test can read the event.
    async with asyncio.timeout(5):
        while not CONFIRMATIONS.waiting:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    (call,) = CONFIRMATIONS.waiting
    return call


async def _answer(
    client: httpx2.AsyncClient, searxng: FakeSearxng, is_allowed: bool
) -> httpx2.Response:
    """Answers the search that waits, after checking that nothing was sent yet."""
    conversation_id, tool_call_id = await _waiting_call()
    assert searxng.requests == []
    return await client.post(
        f"/api/conversations/{conversation_id}/tool-calls/{tool_call_id}/confirmations",
        json={"is_allowed": is_allowed},
    )


async def test_allowed_search_runs_and_the_answer_cites_the_page(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins aktuell")]
    searxng.results = [SNB_PAGE]

    response, confirmation = await asyncio.gather(
        _stream(client=client, url=url),
        _answer(client=client, searxng=searxng, is_allowed=True),
    )

    assert confirmation.status_code == 204
    assert searxng.requests == [{"q": "SNB Leitzins aktuell", "format": "json"}]
    events = sse_events(response=response)
    asked = [data for name, data in events if name == "tool_call"]
    assert [(call["confirmation"], call["arguments"]) for call in asked] == [
        (CONFIRMATION, {"query": "SNB Leitzins aktuell"})
    ]
    sources = events[-1][1]["provenance"]["sources"]
    assert [(source["title"], source["url"]) for source in sources] == [
        (SNB_PAGE["title"], SNB_PAGE["url"])
    ]
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["id"] == asked[0]["id"]
    assert (call["tool_name"], call["title"], call["icon"]) == (
        SEARCH_TOOL,
        "Search the web",
        "globe",
    )
    assert call["result"]["results"][0]["snippet"] == SNB_PAGE["content"]
    answer = apertus.requests[-1]["messages"][-1]["content"]
    assert SNB_PAGE["content"] in answer
    assert SNB_PAGE["url"] in answer


async def test_refused_search_sends_nothing_and_the_turn_asks_no_second_time(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins"), _search(query="Leitzins Schweiz")]

    response, confirmation = await asyncio.gather(
        _stream(client=client, url=url),
        _answer(client=client, searxng=searxng, is_allowed=False),
    )

    assert confirmation.status_code == 204
    assert searxng.requests == []
    events = sse_events(response=response)
    assert [data["confirmation"] for name, data in events if name == "tool_call"] == [
        CONFIRMATION,
        None,
    ]
    assert events[-1][0] == "done"
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [(call["result"], call["error"]) for call in calls] == [(None, NOT_ALLOWED)] * 2
    assert NOT_ALLOWED in apertus.requests[-1]["messages"][-1]["content"]


async def test_search_nobody_answers_is_refused(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    searxng: FakeSearxng,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins")]
    monkeypatch.setattr(tool_call_service, "CONFIRMATION_TIMEOUT_SECONDS", 0.01)

    response = await _stream(client=client, url=url)

    assert sse_events(response=response)[-1][0] == "done"
    assert searxng.requests == []
    assert CONFIRMATIONS.waiting == {}
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["error"] == NOT_ALLOWED


async def test_turn_without_a_stream_refuses_the_search(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins")]

    reply = await client.post(f"{url}/messages", json={"content": "SNB-Leitzins?"})

    assert reply.status_code == 201
    assert searxng.requests == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, NOT_ALLOWED)


async def test_search_with_wrong_arguments_asks_nobody(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="")]

    response = await _stream(client=client, url=url)

    events = sse_events(response=response)
    assert [data["confirmation"] for name, data in events if name == "tool_call"] == [None]
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["error"].startswith("Invalid arguments. query:")
    assert searxng.requests == []


async def test_failed_search_goes_back_to_the_model(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins")]
    searxng.status = 500

    response, _ = await asyncio.gather(
        _stream(client=client, url=url),
        _answer(client=client, searxng=searxng, is_allowed=True),
    )

    assert sse_events(response=response)[-1][0] == "done"
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["result"] is None
    assert call["error"] == "Web search failed: HTTPStatusError"


async def test_only_the_waiting_call_of_the_customers_own_conversation_takes_an_answer(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    other = await make_conversation(session=session)
    foreign = await make_conversation(session=session, owner_id=uuid4())
    apertus.decisions = [_search(query="SNB Leitzins")]

    async def answer_elsewhere_first() -> list[int]:
        _, tool_call_id = await _waiting_call()
        codes = []
        for conversation_id in (other.id, foreign.id, conversation.id, conversation.id):
            answered = await client.post(
                f"/api/conversations/{conversation_id}/tool-calls/{tool_call_id}/confirmations",
                json={"is_allowed": True},
            )
            codes.append(answered.status_code)
        return codes

    _, codes = await asyncio.gather(
        _stream(client=client, url=f"/api/conversations/{conversation.id}"),
        answer_elsewhere_first(),
    )

    assert codes == [404, 404, 204, 404]
    assert len(searxng.requests) == 1


async def test_without_an_address_search_is_not_offered(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    app.state.searxng = None

    reply = await client.post(
        f"/api/conversations/{conversation.id}/messages", json={"content": "SNB-Leitzins?"}
    )

    assert reply.status_code == 201
    assert SEARCH_TOOL not in apertus.requests[0]["messages"][0]["content"]
    assert "list_accounts" in apertus.requests[0]["messages"][0]["content"]
