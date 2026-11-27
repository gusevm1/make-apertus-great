import json
from uuid import uuid4

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FAKE_MODEL, FAKE_REPLY, FakeApertus
from tests.factories import make_conversation, make_message


async def test_conversation_lifecycle(client: httpx2.AsyncClient) -> None:
    created = await client.post("/api/conversations", json={"title": "First"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    assert "owner_id" not in created.json()

    listed = await client.get("/api/conversations")
    assert [c["id"] for c in listed.json()] == [conversation_id]

    renamed = await client.patch(f"/api/conversations/{conversation_id}", json={"title": "New"})
    assert renamed.json()["title"] == "New"

    deleted = await client.delete(f"/api/conversations/{conversation_id}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/conversations/{conversation_id}")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"


async def test_message_gets_stored_reply_with_provenance(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    await make_message(session=session, conversation_id=conversation.id, content="Earlier question")
    await make_message(
        session=session, conversation_id=conversation.id, role="assistant", content="Earlier answer"
    )
    url = f"/api/conversations/{conversation.id}/messages"

    reply = await client.post(url, json={"content": "Grüezi"})

    assert reply.status_code == 201
    assert reply.json()["role"] == "assistant"
    assert reply.json()["content"] == FAKE_REPLY
    assert reply.json()["provenance"]["model"] == FAKE_MODEL
    assert reply.json()["provenance"]["latency_ms"] >= 0

    stored = (await client.get(url)).json()
    assert [(m["role"], m["content"]) for m in stored] == [
        ("user", "Earlier question"),
        ("assistant", "Earlier answer"),
        ("user", "Grüezi"),
        ("assistant", FAKE_REPLY),
    ]
    sent = [(m["role"], m["content"]) for m in apertus.requests[-1]["messages"]]
    assert sent[0][0] == "system"
    assert sent[1:-2] == [("user", "Earlier question"), ("assistant", "Earlier answer")]
    # The question carries the customer block in front.
    assert sent[-2][0] == "user"
    assert sent[-2][1].endswith("</customer>\nGrüezi")
    assert sent[-1][0] == "user"
    assert "Write the answer in the language of that question" in sent[-1][1]


async def test_message_streams_tokens_then_stored_reply(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"

    response = await client.post(url, params={"stream": "true"}, json={"content": "Hallo"})

    blocks = [block.split("\n") for block in response.text.strip().split("\n\n")]
    events = [(lines[0].removeprefix("event: "), json.loads(lines[1][6:])) for lines in blocks]
    assert [name for name, _ in events] == ["planning", "token", "token", "done"]
    assert "".join(data["text"] for name, data in events if name == "token") == FAKE_REPLY
    done = events[-1][1]
    assert done["content"] == FAKE_REPLY
    assert done["provenance"]["model"] == FAKE_MODEL

    stored = (await client.get(url)).json()
    assert [m["role"] for m in stored] == ["user", "assistant"]
    assert stored[-1]["id"] == done["id"]


async def test_other_users_conversation_is_not_found(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    conversation = await make_conversation(session=session, owner_id=uuid4())
    url = f"/api/conversations/{conversation.id}"

    assert (await client.get(url)).status_code == 404
    assert (await client.patch(url, json={"title": "Mine now"})).status_code == 404
    assert (await client.post(f"{url}/messages", json={"content": "Hi"})).status_code == 404
    assert (await client.delete(url)).status_code == 404
    assert (await client.get("/api/conversations")).json() == []


async def test_invalid_input_uses_the_error_shape(client: httpx2.AsyncClient) -> None:
    conversation_id = (await client.post("/api/conversations", json={})).json()["id"]

    empty = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": ""}
    )
    bad_sort = await client.get("/api/conversations", params={"sort": "title"})

    assert empty.status_code == 422
    assert empty.json()["error"] == "validation_error"
    assert empty.json()["fields"][0]["field"] == "content"
    assert bad_sort.status_code == 400
    assert bad_sort.json()["error"] == "bad_request"


async def test_failed_reply_leaves_no_message_behind(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"
    apertus.status = 500

    plain = await client.post(url, json={"content": "Hallo"})
    streamed = await client.post(url, params={"stream": "true"}, json={"content": "Hallo"})

    assert plain.status_code == 502
    assert plain.json()["error"] == "upstream_error"
    assert streamed.text.startswith('event: planning\ndata: {"round": 0}\n\nevent: error\n')
    assert (await client.get(url)).json() == []
