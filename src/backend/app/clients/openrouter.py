import httpx2

from app.clients.apertus import ApertusClient
from app.core.config import Settings


def openrouter_client(
    settings: Settings, model_name: str, http_client: httpx2.AsyncClient | None = None
) -> ApertusClient:
    """An ApertusClient that runs `model_name` on OpenRouter, for evals and tooling only."""
    if settings.openrouter_api_key is None:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return ApertusClient(
        settings=settings.model_copy(
            update={
                "llm_base_url": settings.openrouter_base_url,
                "llm_api_key": settings.openrouter_api_key,
                "llm_name": model_name,
                "llm_name_fast": None,
            }
        ),
        http_client=http_client,
    )
