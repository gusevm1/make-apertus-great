from typing import Annotated, Any

import httpx2
from fastapi import Depends, Request

from app.core.config import Settings
from app.core.errors import UnauthorizedError, UpstreamError


class BankingClient:
    """The e-banking's REST API. The customer's token decides whose data a call returns."""

    def __init__(self, settings: Settings, http_client: httpx2.AsyncClient | None = None) -> None:
        self._http = http_client or httpx2.AsyncClient(
            base_url=settings.banking_api_url, timeout=settings.banking_timeout_seconds
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def get(
        self, path: str, token: str | None = None, params: dict[str, Any] | None = None
    ) -> Any:
        """GET `path` as the customer the token belongs to; only public paths work without one."""
        headers = {} if token is None else {"Authorization": f"Bearer {token}"}
        try:
            response = await self._http.get(path, params=params, headers=headers)
        except httpx2.HTTPError as exc:
            raise UpstreamError("The banking API is unreachable") from exc
        if response.status_code == 401:
            raise UnauthorizedError("The e-banking session is missing or has ended")
        if response.is_error:
            raise UpstreamError(f"The banking API returned {response.status_code}")
        return response.json()


def get_banking_client(request: Request) -> BankingClient:
    return request.app.state.banking


BankingClientDep = Annotated[BankingClient, Depends(get_banking_client)]
