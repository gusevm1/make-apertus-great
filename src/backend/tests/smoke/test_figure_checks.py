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
