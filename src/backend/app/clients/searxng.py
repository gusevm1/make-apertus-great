from typing import Annotated

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
            return SearxngSearch.model_validate_json(response.content).results
        except (httpx2.HTTPError, ValidationError) as exc:
            raise UpstreamError(f"Web search failed: {type(exc).__name__}") from exc


def create_searxng_client(settings: Settings) -> SearxngClient | None:
    """The client, or None without SearXNG's address: then web search is not offered."""
    if settings.searxng_url == "":
        return None
    return SearxngClient(settings=settings)


def get_searxng_client(request: Request) -> SearxngClient | None:
    return request.app.state.searxng


SearxngClientDep = Annotated[SearxngClient | None, Depends(get_searxng_client)]
