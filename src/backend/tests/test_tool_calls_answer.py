import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FAKE_REPLY, FakeApertus
from tests.factories import make_conversation


async def test_a_turn_without_streaming_still_streams_its_answer_from_apertus(
    client: httpx2.AsyncClient, apertus: FakeApertus, session: AsyncSession
) -> None:
    conversation = await make_conversation(session=session)

    reply = await client.post(
        f"/api/conversations/{conversation.id}/messages", json={"content": "Hi"}
    )

    assert reply.status_code == 201
    assert reply.json()["content"] == FAKE_REPLY
    # The timeout then counts the wait for the next chunk, so a slow but steady answer finishes.
    answers = [body for body in apertus.requests if "temperature" not in body]
    assert [body.get("stream") for body in answers] == [True]
