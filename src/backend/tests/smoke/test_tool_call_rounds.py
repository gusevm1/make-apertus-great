from typing import Any

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import FakeApertus
from tests.factories import make_conversation
from tests.lookup_tool import LOOKUP
from tests.sse import sse_events

pytestmark = pytest.mark.usefixtures("lookup_tool")


def _decision(plan: str, tool: str, **arguments: Any) -> str:
    request = ToolRequest(reason="Because.", tool=tool, arguments=arguments)
    return ToolDecision(plan=plan, calls=[request]).model_dump_json()


async def test_tool_calls_store_their_title_icon_round_and_plan(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [
        _decision(plan="Look up Zurich.", tool=LOOKUP.name, query="Zurich"),
        _decision(plan="Now the transfer.", tool="transfer_money"),
    ]

    reply = await client.post(f"{url}/messages", json={"content": "Zürich und Überweisung?"})

    assert reply.status_code == 201
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [(call["round"], call["plan"], call["title"], call["icon"]) for call in calls] == [
        (0, "Look up Zurich.", "Look it up", "search"),
        (1, "Now the transfer.", "transfer_money", "circle-help"),
    ]


async def test_stream_announces_each_round_and_labels_each_call(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(plan="Look up Zurich.", tool=LOOKUP.name, query="Zurich")]

    response = await client.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "Was steht über Zürich?"}
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
    assert [data for name, data in events if name == "planning"] == [{"round": 0}, {"round": 1}]
    call = events[1][1]
    assert call["title"] == "Look it up"
    assert call["icon"] == "search"
    assert call["round"] == 0
    assert call["plan"] == "Look up Zurich."
    stored = (await client.get(f"{url}/tool-calls")).json()
    assert [(row["id"], row["round"], row["plan"]) for row in stored] == [
        (call["id"], 0, "Look up Zurich.")
    ]
