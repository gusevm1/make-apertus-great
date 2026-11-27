import pytest

from app.clients.searxng import SearxngClient, create_searxng_client
from app.core.config import get_settings
from app.core.errors import UpstreamError
from app.features.web_search.service import SNIPPET_MAX_CHARS, WebSearchService, trim
from tests.conftest import FakeSearxng


def _page(number: int, score: float, content: str = "Text.") -> dict[str, object]:
    return {
        "title": f"Page {number}",
        "url": f"https://example.ch/{number}",
        "content": content,
        "score": score,
    }


async def test_search_keeps_the_five_best_pages(
    searxng: FakeSearxng, searxng_client: SearxngClient
) -> None:
    searxng.results = [_page(number=number, score=number / 10) for number in range(7)]

    found = await WebSearchService(searxng=searxng_client).search_web(query="SNB Leitzins")

    assert searxng.requests == [{"q": "SNB Leitzins", "format": "json"}]
    assert [page.title for page in found.results] == [f"Page {n}" for n in (6, 5, 4, 3, 2)]
    assert [(source.title, source.url) for source in found.sources] == [
        (page.title, page.url) for page in found.results
    ]


async def test_search_takes_a_page_without_a_snippet(
    searxng: FakeSearxng, searxng_client: SearxngClient
) -> None:
    searxng.results = [{"title": "Page", "url": "https://example.ch/page", "score": 1.5}]

    found = await WebSearchService(searxng=searxng_client).search_web(query="SNB")

    assert [(page.title, page.snippet) for page in found.results] == [("Page", "")]


async def test_search_fails_with_an_upstream_error(
    searxng: FakeSearxng, searxng_client: SearxngClient
) -> None:
    searxng.status = 429

    with pytest.raises(UpstreamError, match="Web search failed"):
        await WebSearchService(searxng=searxng_client).search_web(query="SNB")


async def test_search_fails_when_no_search_engine_answered(
    searxng: FakeSearxng, searxng_client: SearxngClient
) -> None:
    searxng.unresponsive_engines = [["google", "access denied"], ["duckduckgo", "timeout"]]

    with pytest.raises(UpstreamError, match="the search engines did not answer"):
        await WebSearchService(searxng=searxng_client).search_web(query="SNB")


async def test_search_without_a_match_finds_nothing(
    searxng: FakeSearxng, searxng_client: SearxngClient
) -> None:
    found = await WebSearchService(searxng=searxng_client).search_web(query="qwertzuiop")

    assert found.results == []


def test_trim_keeps_short_text_on_one_line() -> None:
    assert trim(text="Der Leitzins\n  liegt bei 0 %.") == "Der Leitzins liegt bei 0 %."


def test_trim_cuts_long_text_at_a_word() -> None:
    snippet = trim(text="Zins " * 200)

    assert len(snippet) <= SNIPPET_MAX_CHARS
    assert snippet.endswith("Zins…")


def test_no_client_without_an_address() -> None:
    settings = get_settings().model_copy(update={"searxng_url": ""})

    assert create_searxng_client(settings=settings) is None
