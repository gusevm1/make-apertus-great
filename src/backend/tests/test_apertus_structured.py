import json

import httpx2
from pydantic import BaseModel

from app.clients.apertus import ApertusClient, Message, Model
from app.core.config import get_settings
from tests.conftest import _fake_completion


class Decision(BaseModel):
    tool: str


def _client(replies: list[str]) -> tuple[ApertusClient, list[dict]]:
    requests: list[dict] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        requests.append(body)
        return _fake_completion(body=body, content=replies.pop(0))

    fake_http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    return ApertusClient(settings=get_settings(), http_client=fake_http), requests


async def test_a_second_object_after_the_json_is_ignored() -> None:
    client, requests = _client(replies=['{"tool": "search_movements"}\n{"tool": "list_accounts"}'])

    result = await client.structured(
        [Message(role="user", content="Migros in October?")],
        schema=Decision,
        model=Model.SMART,
        purpose="test",
    )

    assert result.content == Decision(tool="search_movements")
    assert len(requests) == 1


async def test_a_note_after_the_json_is_ignored() -> None:
    client, _ = _client(replies=['{"tool": "list_accounts"} I chose the accounts.'])

    result = await client.structured(
        [Message(role="user", content="My accounts?")],
        schema=Decision,
        model=Model.SMART,
        purpose="test",
    )

    assert result.content == Decision(tool="list_accounts")
