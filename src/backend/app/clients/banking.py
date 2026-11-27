from typing import Annotated, Any, Literal

import httpx2
from fastapi import Depends, Request

from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotInBankError,
    UnauthorizedError,
    UpstreamError,
)


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
        return self._data(response=response)

    async def write(
        self,
        method: Literal["POST", "PATCH", "DELETE"],
        path: str,
        token: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Change the bank as the customer; None when it answers with no content."""
        try:
            response = await self._http.request(
                method, path, json=body, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx2.HTTPError as exc:
            raise UpstreamError("The banking API is unreachable") from exc
        if response.status_code == 204:
            return None
        return self._data(response=response)

    async def upload_document(
        self, token: str, content: bytes, filename: str, content_type: str | None
    ) -> Any:
        """Store a file in the customer's documents, inside the bank's environment."""
        try:
            response = await self._http.post(
                "/documents",
                files={"file": (filename, content, content_type or "application/octet-stream")},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx2.HTTPError as exc:
            raise UpstreamError("The banking API is unreachable") from exc
        return self._data(response=response)

    async def delete_document(self, token: str, document_id: str) -> None:
        """Remove a file from the customer's documents; one the bank lacks counts as removed."""
        try:
            response = await self._http.delete(
                f"/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
            )
        except httpx2.HTTPError as exc:
            raise UpstreamError("The banking API is unreachable") from exc
        # After /admin/reset the bank has forgotten the file.
        if response.status_code != 404 and response.is_error:
            self._data(response=response)

    def _data(self, response: httpx2.Response) -> Any:
        if response.status_code == 401:
            raise UnauthorizedError("The e-banking session is missing or has ended")
        if response.status_code == 404:
            raise NotInBankError(f"The banking API refused the request: {response.text[:300]}")
        if response.status_code == 422:
            # The id or a filter was wrong; the caller, often the model, can correct it.
            raise BadRequestError(f"The banking API refused the request: {response.text[:300]}")
        if response.status_code == 409:
            # Such as a change to a payment that is no longer pending.
            raise ConflictError(f"The banking API refused the change: {response.text[:300]}")
        if response.is_error:
            raise UpstreamError(f"The banking API returned {response.status_code}")
        return response.json()


def get_banking_client(request: Request) -> BankingClient:
    return request.app.state.banking


BankingClientDep = Annotated[BankingClient, Depends(get_banking_client)]
