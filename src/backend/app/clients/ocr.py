from typing import Annotated

import httpx2
from fastapi import Depends, Request

from app.core.config import Settings
from app.core.errors import UpstreamError


class OcrClient:
    """The e-banking's OCR service: a document in, its text as Markdown out. It stores nothing."""

    def __init__(self, settings: Settings, http_client: httpx2.AsyncClient | None = None) -> None:
        # One page takes 1 to 4 seconds and the service reads one document at a time.
        self._http = http_client or httpx2.AsyncClient(
            base_url=settings.ocr_url, timeout=settings.ocr_timeout_seconds
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def convert(self, content: bytes, filename: str) -> str:
        """The document's text as Markdown; the service picks its reader from the file name."""
        try:
            response = await self._http.post("/convert", files={"file": (filename, content)})
        except httpx2.HTTPError as exc:
            raise UpstreamError("The OCR service is unreachable") from exc
        if response.is_error:
            raise UpstreamError(f"The OCR service returned {response.status_code}")
        return response.json()["markdown"]


def get_ocr_client(request: Request) -> OcrClient:
    return request.app.state.ocr


OcrClientDep = Annotated[OcrClient, Depends(get_ocr_client)]
