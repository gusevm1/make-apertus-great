import json
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient
from app.core.config import get_settings
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.features.tool_calls.service import MAX_TOOL_CALLS, MAX_TOOL_ROUNDS
from app.main import app
from tests.conftest import FAKE_MODEL, FAKE_REPLY, FAKE_USAGE, NO_TOOL_DECISION, FakeApertus
from tests.factories import make_conversation
from tests.lookup_tool import LOOKUP
from tests.sse import sse_events

GUARDRAIL_OK = {"name": "guardrail", "passed": True, "detail": "ok"}

pytestmark = pytest.mark.usefixtures("lookup_tool")
PAGES = ["https://example.ch/Zurich", "https://example.ch/shared"]


def _calls(*requests: ToolRequest) -> str:
    return ToolDecision(plan="Look it up.", calls=list(requests)).model_dump_json()


def _call(tool: str, **arguments: Any) -> str:
    return _calls(ToolRequest(reason="Because.", tool=tool, arguments=arguments))


def _lookup(query: str, reason: str = "Because.") -> ToolRequest:
    return ToolRequest(reason=reason, tool=LOOKUP.name, arguments={"query": query})


async def test_message_uses_a_tool_then_gets_its_reply(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call(LOOKUP.name, query="Zurich")]

    reply = await client.post(f"{url}/messages", json={"content": "Was steht über Zürich?"})

    assert reply.status_code == 201
    assert reply.json()["content"] == FAKE_REPLY
    provenance = reply.json()["provenance"]
    assert provenance["model"] == FAKE_MODEL
    assert [source["id"] for source in provenance["sources"]] == PAGES
    assert provenance["checks"] == [
        {"name": "tool_calls_valid", "passed": True, "detail": "1 of 1"},
        GUARDRAIL_OK,
    ]

    messages = (await client.get(f"{url}/messages")).json()
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [(call["position"], call["tool_name"], call["error"]) for call in calls] == [
        (0, LOOKUP.name, None)
    ]
    assert calls[0]["message_id"] == messages[0]["id"]
    assert calls[0]["arguments"] == {"query": "Zurich"}
    assert calls[0]["result"]["text"] == "Page about Zurich"
    assert calls[0]["provenance"]["model"] == FAKE_MODEL

    decision, next_decision, answer = apertus.requests
    assert LOOKUP.name in decision["messages"][0]["content"]
    assert f'<tool_result tool="{LOOKUP.name}">' in next_decision["messages"][-2]["content"]
    assert answer["messages"][1] == {"role": "user", "content": "Was steht über Zürich?"}
    assert "Page about Zurich" in answer["messages"][-1]["content"]


async def test_message_without_a_tool_leaves_no_tool_calls(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"

    reply = await client.post(f"{url}/messages", json={"content": "What is an IBAN?"})

    assert reply.status_code == 201
    assert reply.json()["provenance"]["sources"] == []
    assert reply.json()["provenance"]["checks"] == [GUARDRAIL_OK]
    assert (await client.get(f"{url}/tool-calls")).json() == []
    assert len(apertus.requests) == 2


async def test_empty_tool_name_counts_as_no_tool(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call("")]

    reply = await client.post(f"{url}/messages", json={"content": "Hallo"})

    assert reply.status_code == 201
    assert reply.json()["provenance"]["checks"] == [GUARDRAIL_OK]
    assert (await client.get(f"{url}/tool-calls")).json() == []


async def test_follow_up_sees_the_earlier_turns(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.decisions = [_call(LOOKUP.name, query="New York")]
    await client.post(url, json={"content": "Was steht über New York?"})

    await client.post(url, json={"content": "Und über Tokyo?"})

    decision, answer = apertus.requests[-2:]
    for history in (decision["messages"][1:-1], answer["messages"][1:-1]):
        assert [(message["role"], message["content"]) for message in history] == [
            ("user", "Was steht über New York?"),
            ("assistant", FAKE_REPLY),
            ("user", "Und über Tokyo?"),
        ]


async def test_wrong_tool_call_goes_back_to_the_model_as_an_error(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [
        _call("transfer_money", amount=5000),
        _call(LOOKUP.name, query=5),
        _call(LOOKUP.name, query="missing"),
    ]

    reply = await client.post(f"{url}/messages", json={"content": "Send 5000 CHF"})

    assert reply.status_code == 201
    assert reply.json()["provenance"]["sources"] == []
    assert reply.json()["provenance"]["checks"] == [
        {"name": "tool_calls_valid", "passed": False, "detail": "0 of 3"},
        GUARDRAIL_OK,
    ]
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [call["result"] for call in calls] == [None, None, None]
    assert calls[0]["error"].startswith("Unknown tool 'transfer_money'")
    assert calls[1]["error"] == "Invalid arguments. query: Input should be a valid string"
    assert calls[2]["error"] == "No page for 'missing'. Send a town instead."
    assert "Unknown tool 'transfer_money'" in apertus.requests[1]["messages"][-2]["content"]
    assert "Input should be a valid string" in apertus.requests[2]["messages"][-2]["content"]
    assert "Send a town instead." in apertus.requests[-1]["messages"][-1]["content"]


async def test_repeated_call_ends_the_tool_phase(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call(LOOKUP.name, query="Tokyo")] * 3

    reply = await client.post(f"{url}/messages", json={"content": "Und über Tokyo?"})

    assert reply.status_code == 201
    assert len((await client.get(f"{url}/tool-calls")).json()) == 1
    assert len(apertus.decisions) == 1


async def test_tool_calls_stop_at_the_limit_and_the_reply_still_comes(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    towns = [
        "Zurich",
        "Paris",
        "Rome",
        "Tokyo",
        "Seoul",
        "Bern",
        "Basel",
        "Shanghai",
        "London",
        "New York",
    ]
    assert len(towns) == MAX_TOOL_CALLS + 2
    apertus.decisions = [_calls(*(_lookup(query=town) for town in towns)), _call(LOOKUP.name)]

    reply = await client.post(f"{url}/messages", json={"content": "Look it up."})

    assert reply.status_code == 201
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [call["arguments"]["query"] for call in calls] == towns[:MAX_TOOL_CALLS]
    assert len(apertus.decisions) == 1


async def test_one_decision_runs_all_its_calls_and_identical_ones_once(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [
        _calls(
            _lookup(query="Zurich", reason="Genf"),
            _lookup(query="Zurich", reason="Basel"),
            _lookup(query="Mumbai", reason="Mumbai"),
        )
    ]

    reply = await client.post(f"{url}/messages", json={"content": "Genf, Basel und Mumbai?"})

    assert reply.status_code == 201
    assert reply.json()["provenance"]["checks"][0]["detail"] == "2 of 2"
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [call["result"]["text"] for call in calls] == ["Page about Zurich", "Page about Mumbai"]
    assert [call["reason"] for call in calls] == ["Genf; Basel", "Mumbai"]
    assert [call["position"] for call in calls] == [0, 1]
    results = apertus.requests[1]["messages"][-2]["content"]
    assert results.count("<tool_result") == 2
    assert "Asked for: Genf; Basel" in results
    assert len(apertus.requests) == 3


async def test_a_failed_call_in_a_batch_leaves_the_other_results(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [
        _calls(_lookup(query="Zurich"), _lookup(query="missing"), _lookup(query="Bern"))
    ]

    reply = await client.post(f"{url}/messages", json={"content": "Zurich, missing, Bern?"})

    assert reply.status_code == 201
    assert reply.json()["provenance"]["checks"][0]["detail"] == "2 of 3"
    zurich, missing, bern = (await client.get(f"{url}/tool-calls")).json()
    assert zurich["result"]["text"] == "Page about Zurich"
    assert missing["result"] is None
    assert missing["error"] == "No page for 'missing'. Send a town instead."
    assert bern["result"]["text"] == "Page about Bern"


async def test_decisions_stop_after_the_last_round(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    towns = ["Zurich", "Paris", "Rome", "Tokyo", "Seoul", "Bern"]
    assert len(towns) == MAX_TOOL_ROUNDS + 2
    apertus.decisions = [_call(LOOKUP.name, query=town) for town in towns]

    reply = await client.post(f"{url}/messages", json={"content": "Look it up."})

    assert reply.status_code == 201
    assert len((await client.get(f"{url}/tool-calls")).json()) == MAX_TOOL_ROUNDS
    assert len(apertus.decisions) == 2


async def test_failed_turn_leaves_no_tool_calls_behind(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call(LOOKUP.name), "not json", "still not json"]

    reply = await client.post(f"{url}/messages", json={"content": "Look it up."})

    assert reply.status_code == 502
    assert reply.json()["error"] == "upstream_error"
    assert (await client.get(f"{url}/messages")).json() == []
    assert (await client.get(f"{url}/tool-calls")).json() == []


async def test_streamed_message_uses_a_tool_then_streams_the_reply(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call(LOOKUP.name)]

    response = await client.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "Hallo"}
    )

    events = sse_events(response=response)
    assert [name for name, _ in events] == [
        "planning",
        "tool_call",
        "tool_result",
        "planning",
        "token",
        "token",
        "done",
    ]
    assert events[-1][1]["content"] == FAKE_REPLY
    sources = events[-1][1]["provenance"]["sources"]
    assert [source["id"] for source in sources] == PAGES
    assert len((await client.get(f"{url}/tool-calls")).json()) == 1


async def test_streamed_message_shows_each_tool_call_with_its_result(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call("transfer_money"), _call(LOOKUP.name, query="Zurich")]

    response = await client.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "Hallo"}
    )

    events = sse_events(response=response)
    assert [name for name, _ in events[:6]] == [
        "planning",
        "tool_call",
        "tool_result",
        "planning",
        "tool_call",
        "tool_result",
    ]
    wrong_call, wrong_result, call, result = (
        data for name, data in events[:6] if name != "planning"
    )
    assert wrong_call["tool_name"] == "transfer_money"
    assert wrong_result["id"] == wrong_call["id"]
    assert wrong_result["result"] is None
    assert wrong_result["error"].startswith("Unknown tool 'transfer_money'")
    assert call["tool_name"] == LOOKUP.name
    assert call["arguments"] == {"query": "Zurich"}
    assert call["reason"] == "Because."
    assert result["id"] == call["id"]
    assert result["result"]["text"] == "Page about Zurich"
    assert result["error"] is None
    stored = (await client.get(f"{url}/tool-calls")).json()
    assert [stored_call["id"] for stored_call in stored] == [wrong_call["id"], call["id"]]


async def test_streamed_turn_that_fails_after_a_tool_call_ends_with_an_error(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_call(LOOKUP.name), "not json", "still not json"]

    response = await client.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "Hallo"}
    )

    events = sse_events(response=response)
    assert [name for name, _ in events] == [
        "planning",
        "tool_call",
        "tool_result",
        "planning",
        "error",
    ]
    assert events[-1][1]["error"] == "upstream_error"
    assert (await client.get(f"{url}/messages")).json() == []
    assert (await client.get(f"{url}/tool-calls")).json() == []


async def test_other_users_tool_calls_are_not_found(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    conversation = await make_conversation(session=session, owner_id=uuid4())

    response = await client.get(f"/api/conversations/{conversation.id}/tool-calls")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def _scripted_apertus(decision: str, tokens: list[str], requests: list[Any]) -> httpx2.AsyncClient:
    """Fake Apertus HTTP that answers one decision, then streams `tokens` as the answer."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        requests.append(body)
        if not body.get("stream"):
            content = decision if len(requests) == 1 else NO_TOOL_DECISION
            message = {"role": "assistant", "content": content}
            choice = {"index": 0, "finish_reason": "stop", "message": message}
            return httpx2.Response(200, json={"choices": [choice], "usage": FAKE_USAGE})
        chunks = [{"choices": [{"index": 0, "delta": {"content": token}}]} for token in tokens]
        events = "".join(
            f"data: {json.dumps(chunk)}\n\n"
            for chunk in [*chunks, {"choices": [], "usage": FAKE_USAGE}]
        )
        return httpx2.Response(
            200, text=f"{events}data: [DONE]\n\n", headers={"content-type": "text/event-stream"}
        )

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


async def test_streamed_answer_keeps_german_with_ss_but_not_in_urls_or_quotes(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    requests: list[Any] = []
    tokens = ["Grüße", " siehe https://stra", "ße.ch, dort steht «Große", " Straße».\nGruß"]
    fake_http = _scripted_apertus(
        decision=_call(LOOKUP.name, query="Zurich"), tokens=tokens, requests=requests
    )
    faked_apertus = app.state.apertus
    app.state.apertus = ApertusClient(settings=get_settings(), http_client=fake_http)
    try:
        response = await client.post(
            f"{url}/messages",
            params={"stream": "true"},
            json={"content": "Wie ist das Wetter in Zürich?"},
        )
    finally:
        await app.state.apertus.close()
        app.state.apertus = faked_apertus

    events = sse_events(response=response)
    assert [data["text"] for name, data in events if name == "token"] == [
        "Grüsse",
        " siehe https://stra",
        "ße.ch, dort steht «Große",
        " Straße».\nGruss",
    ]
    answer = "Grüsse siehe https://straße.ch, dort steht «Große Straße».\nGruss"
    assert events[-1][1]["content"] == answer
    stored = (await client.get(f"{url}/messages")).json()
    assert stored[-1]["content"] == answer
    prompt = requests[-1]["messages"]
    assert "standard written German with Swiss spelling" in prompt[0]["content"]
    assert "never Swiss German dialect" in prompt[0]["content"]
    assert "written in German, so write the whole answer in German" in prompt[-1]["content"]
