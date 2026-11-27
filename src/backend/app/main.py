from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app.clients.apertus import ApertusClient
from app.clients.banking import BankingClient
from app.clients.ocr import OcrClient
from app.clients.searxng import create_searxng_client
from app.core.auth import require_allowed_origin
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import register_error_handlers
from app.features.context_entries.controller import router as context_entries_router
from app.features.conversations.controller import router as conversations_router
from app.features.documents.controller import router as documents_router
from app.features.transcriptions.controller import router as transcriptions_router

public_router = APIRouter()


@public_router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check for deployment."""
    return {"status": "ok"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.apertus = ApertusClient(settings=get_settings())
    app.state.banking = BankingClient(settings=get_settings())
    app.state.ocr = OcrClient(settings=get_settings())
    app.state.searxng = create_searxng_client(settings=get_settings())
    yield
    await app.state.apertus.close()
    await app.state.banking.close()
    await app.state.ocr.close()
    if app.state.searxng is not None:
        await app.state.searxng.close()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrustRoom API",
        lifespan=lifespan,
        dependencies=[Depends(require_allowed_origin)],
    )
    register_error_handlers(app=app)
    app.include_router(public_router, prefix="/api")
    app.include_router(context_entries_router, prefix="/api")
    app.include_router(conversations_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(transcriptions_router, prefix="/api")
    return app


app = create_app()
