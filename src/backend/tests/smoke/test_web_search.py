import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.main import app
from tests.conftest import FakeApertus, FakeSearxng
from tests.factories import make_conversation

SEARCH_TOOL = "search_web"
SNB_PAGE = {
    "title": "Geldpolitische Lagebeurteilung",
    "url": "https://www.snb.ch/de/publications/communication/press-releases",
    "content": "Die SNB belässt den SNB-Leitzins bei 0 %.",
    "score": 0.9,
}


def _search(query: str) -> str:
    request = ToolRequest(reason="Current rate.", tool=SEARCH_TOOL, arguments={"query": query})
    return ToolDecision(plan="Search the web.", calls=[request]).model_dump_json()


async def test_turn_searches_the_web_and_cites_the_page(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins aktuell")]
    searxng.results = [SNB_PAGE]

    reply = await client.post(
        f"{url}/messages", json={"content": "Wie hoch ist der SNB-Leitzins aktuell?"}
    )

    assert reply.status_code == 201
    assert searxng.requests == [{"q": "SNB Leitzins aktuell", "format": "json"}]
    sources = reply.json()["provenance"]["sources"]
    assert [(source["title"], source["url"]) for source in sources] == [
        (SNB_PAGE["title"], SNB_PAGE["url"])
    ]
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["tool_name"], call["title"], call["icon"]) == (
        SEARCH_TOOL,
        "Search the web",
        "globe",
    )
    assert call["result"]["results"][0]["snippet"] == SNB_PAGE["content"]
    answer = apertus.requests[-1]["messages"][-1]["content"]
    assert SNB_PAGE["content"] in answer
    assert SNB_PAGE["url"] in answer


async def test_failed_search_goes_back_to_the_model(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, searxng: FakeSearxng
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_search(query="SNB Leitzins")]
    searxng.status = 500

    reply = await client.post(f"{url}/messages", json={"content": "SNB-Leitzins?"})

    assert reply.status_code == 201
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["result"] is None
    assert call["error"] == "Web search failed: HTTPStatusError"


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
