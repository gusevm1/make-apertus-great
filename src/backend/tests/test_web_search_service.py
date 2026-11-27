import pytest
from pydantic import SecretStr

from app.clients.tavily import TavilyClient, create_tavily_client
from app.core.config import get_settings
from app.core.errors import UpstreamError
from app.features.web_search.service import SNIPPET_MAX_CHARS, WebSearchService, trim
from tests.conftest import FakeTavily


def _page(number: int, score: float, content: str = "Text.") -> dict[str, object]:
    return {
        "title": f"Page {number}",
        "url": f"https://example.ch/{number}",
        "content": content,
        "score": score,
    }


async def test_search_keeps_the_five_best_pages(
    tavily: FakeTavily, tavily_client: TavilyClient
) -> None:
    tavily.results = [_page(number=number, score=number / 10) for number in range(7)]

    found = await WebSearchService(tavily=tavily_client).search_web(query="SNB Leitzins")

    assert tavily.requests == [{"query": "SNB Leitzins", "max_results": 5}]
    assert [page.title for page in found.results] == [f"Page {n}" for n in (6, 5, 4, 3, 2)]
    assert [(source.title, source.url) for source in found.sources] == [
        (page.title, page.url) for page in found.results
    ]


async def test_search_fails_with_an_upstream_error(
    tavily: FakeTavily, tavily_client: TavilyClient
) -> None:
    tavily.status = 432

    with pytest.raises(UpstreamError, match="Web search failed"):
        await WebSearchService(tavily=tavily_client).search_web(query="SNB")


def test_trim_keeps_short_text_on_one_line() -> None:
    assert trim(text="Der Leitzins\n  liegt bei 0 %.") == "Der Leitzins liegt bei 0 %."


def test_trim_cuts_long_text_at_a_word() -> None:
    snippet = trim(text="Zins " * 200)

    assert len(snippet) <= SNIPPET_MAX_CHARS
    assert snippet.endswith("Zins…")


def test_no_client_without_a_key() -> None:
    settings = get_settings().model_copy(update={"tavily_api_key": SecretStr("")})

    assert create_tavily_client(settings=settings) is None
