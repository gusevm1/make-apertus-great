import json

import httpx2
from pydantic import SecretStr

from app.clients.apertus import Model
from app.clients.openrouter import openrouter_client
from app.core.config import get_settings


async def test_openrouter_client_sends_its_own_key_and_model_to_openrouter() -> None:
    requests: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "id": "1",
                "object": "chat.completion",
                "created": 0,
                "model": "some/model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "hi"},
                    }
                ],
            },
        )

    settings = get_settings().model_copy(update={"openrouter_api_key": SecretStr("or-key")})
    client = openrouter_client(
        settings=settings,
        model_name="some/model",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handle)),
    )

    result = await client.chat(
        messages=[{"role": "user", "content": "hello"}], model=Model.FAST, purpose="test"
    )

    assert result.content == "hi"
    assert result.model == "some/model"
    assert str(requests[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer or-key"
    assert json.loads(requests[0].content)["model"] == "some/model"
