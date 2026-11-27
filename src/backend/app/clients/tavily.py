from typing import Annotated

import httpx2
from fastapi import Depends, Request
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import UpstreamError

TIMEOUT_SECONDS = 20


class TavilyResult(BaseModel):
    title: str
    url: str
    content: str
    score: float


class TavilySearch(BaseModel):
    results: list[TavilyResult]


class TavilyClient:
    def __init__(self, settings: Settings, http_client: httpx2.AsyncClient | None = None) -> None:
        if http_client is None:
            http_client = httpx2.AsyncClient(timeout=TIMEOUT_SECONDS)
        self._http = http_client
        self._url = f"{settings.tavily_base_url}/search"
        self._headers = {"Authorization": f"Bearer {settings.tavily_api_key.get_secret_value()}"}

    async def close(self) -> None:
        await self._http.aclose()

    async def search(self, query: str, max_results: int) -> list[TavilyResult]:
        """Search the web; UpstreamError if Tavily fails."""
        try:
            response = await self._http.post(
                self._url,
                headers=self._headers,
                json={"query": query, "max_results": max_results},
            )
            response.raise_for_status()
            return TavilySearch.model_validate_json(response.content).results
        except (httpx2.HTTPError, ValidationError) as exc:
            raise UpstreamError(f"Web search failed: {type(exc).__name__}") from exc


def create_tavily_client(settings: Settings) -> TavilyClient | None:
    """The client, or None without a key: then web search is not offered."""
    if settings.tavily_api_key.get_secret_value() == "":
        return None
    return TavilyClient(settings=settings)


def get_tavily_client(request: Request) -> TavilyClient | None:
    return request.app.state.tavily


TavilyClientDep = Annotated[TavilyClient | None, Depends(get_tavily_client)]
