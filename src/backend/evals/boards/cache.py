"""Every OpenRouter reply on disk, so a rerun of a prompt already sent costs nothing.

The key is the request body (model, messages, parameters) plus a `run` label: three cold runs of
the same prompt are three labels, three entries, and each is free when it runs again.
"""

import contextvars
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx2

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
# OpenRouter's price of z-ai/glm-5.3, dollars per million tokens.
PRICE_IN_PER_M = 0.07
PRICE_OUT_PER_M = 1.40

# aread() has decoded the body, so these no longer describe it.
HOP_HEADERS = {"content-encoding", "content-length", "transfer-encoding"}

run_label: contextvars.ContextVar[str] = contextvars.ContextVar("run_label", default="")


@dataclass
class Spend:
    calls: int = 0
    cached: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    by_model: dict[str, int] = field(default_factory=dict)

    @property
    def dollars(self) -> float:
        return (self.tokens_in * PRICE_IN_PER_M + self.tokens_out * PRICE_OUT_PER_M) / 1_000_000

    def line(self) -> str:
        return (
            f"{self.calls} calls sent, {self.cached} from cache, {self.tokens_in} tokens in, "
            f"{self.tokens_out} out, about ${self.dollars:.4f}"
        )


class CachingTransport(httpx2.AsyncBaseTransport):
    """Answers a request it has seen under the same run label from disk."""

    def __init__(self, directory: Path = CACHE_DIR) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.inner = httpx2.AsyncHTTPTransport()
        self.spend = Spend()

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        body = request.content
        digest = hashlib.sha256(
            run_label.get().encode() + b"\0" + request.url.path.encode() + b"\0" + body
        ).hexdigest()
        path = self.directory / f"{digest}.json"
        if path.exists():
            self.spend.cached += 1
            stored = json.loads(path.read_text(encoding="utf-8"))
            return httpx2.Response(200, json=stored, request=request)
        response = await self.inner.handle_async_request(request)
        content = await response.aread()
        if response.status_code == 200:
            data = json.loads(content)
            usage = data.get("usage") or {}
            self.spend.calls += 1
            self.spend.tokens_in += usage.get("prompt_tokens") or 0
            self.spend.tokens_out += usage.get("completion_tokens") or 0
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return httpx2.Response(
            response.status_code,
            headers=[(k, v) for k, v in response.headers.items() if k.lower() not in HOP_HEADERS],
            content=content,
            request=request,
        )

    async def aclose(self) -> None:
        await self.inner.aclose()
