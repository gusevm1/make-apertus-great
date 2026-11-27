from app.clients.searxng import SearxngClient
from app.core.provenance import ResultSource
from app.features.web_search.schemas import WebPage, WebSearch

MAX_RESULTS = 5
# Five snippets, titles and URLs, twice, stay below the harness's 4000-character cut.
SNIPPET_MAX_CHARS = 350


class WebSearchService:
    def __init__(self, searxng: SearxngClient) -> None:
        self.searxng = searxng

    async def search_web(self, query: str) -> WebSearch:
        """The best five pages for the query, each with a trimmed snippet."""
        found = await self.searxng.search(query=query)
        best = sorted(found, key=lambda result: result.score, reverse=True)[:MAX_RESULTS]
        return WebSearch(
            query=query,
            results=[
                WebPage(title=page.title, url=page.url, snippet=trim(text=page.content))
                for page in best
            ],
            sources=[ResultSource(title=page.title, url=page.url) for page in best],
        )


def trim(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= SNIPPET_MAX_CHARS:
        return flat
    cut = flat[: SNIPPET_MAX_CHARS - 1].rsplit(" ", 1)[0]
    return f"{cut}…"
