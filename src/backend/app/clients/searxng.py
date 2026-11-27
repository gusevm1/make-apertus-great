from typing import Annotated, Any

import httpx2
from fastapi import Depends, Request
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import UpstreamError

TIMEOUT_SECONDS = 20


class SearxngResult(BaseModel):
    title: str
    url: str
    # Some search engines find a page without a snippet.
    content: str = ""
    score: float


class SearxngSearch(BaseModel):
    results: list[SearxngResult]
    # The search engines that did not answer, each with its reason.
    unresponsive_engines: list[Any] = []


class SearxngClient:
    def __init__(self, settings: Settings, http_client: httpx2.AsyncClient | None = None) -> None:
        if http_client is None:
            http_client = httpx2.AsyncClient(timeout=TIMEOUT_SECONDS)
        self._http = http_client
        self._url = f"{settings.searxng_url}/search"

    async def close(self) -> None:
        await self._http.aclose()

    async def search(self, query: str) -> list[SearxngResult]:
        """Search the web; UpstreamError if SearXNG fails."""
        try:
            response = await self._http.get(self._url, params={"q": query, "format": "json"})
            response.raise_for_status()
            search = SearxngSearch.model_validate_json(response.content)
        except (httpx2.HTTPError, ValidationError) as exc:
            raise UpstreamError(f"Web search failed: {type(exc).__name__}") from exc
        # SearXNG answers 200 without a page when the search engines block it.
        if len(search.results) == 0 and len(search.unresponsive_engines) > 0:
            raise UpstreamError("Web search failed: the search engines did not answer")
        return search.results


def create_searxng_client(settings: Settings) -> SearxngClient | None:
    """The client, or None without SearXNG's address: then web search is not offered."""
    if settings.searxng_url == "":
        return None
    return SearxngClient(settings=settings)


def get_searxng_client(request: Request) -> SearxngClient | None:
    return request.app.state.searxng


SearxngClientDep = Annotated[SearxngClient | None, Depends(get_searxng_client)]
