import json
from typing import Any

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.guardrails.prompts import PROMPTS
from tests.conftest import ADVISOR_NAME, ADVISOR_PHONE, FAKE_REPLY, FakeApertus
from tests.factories import make_conversation
from tests.sse import sse_events

ADVISOR_EN = PROMPTS["advisor_en"].format(name=ADVISOR_NAME, phone=ADVISOR_PHONE)
ADVISOR_DE = PROMPTS["advisor_de"].format(name=ADVISOR_NAME, phone=ADVISOR_PHONE)


def check(category: str, language: str = "en") -> str:
    return json.dumps({"category": category, "language": language})


async def ask(client: httpx2.AsyncClient, session: AsyncSession, content: str) -> dict[str, Any]:
    conversation = await make_conversation(session=session)
    reply = await client.post(
        f"/api/conversations/{conversation.id}/messages", json={"content": content}
    )
    assert reply.status_code == 201
    return reply.json()


@pytest.mark.parametrize(
    ("category", "language", "pointer"),
    [
        ("product_choice", "en", ADVISOR_EN),
        ("forecast", "de", ADVISOR_DE),
        ("tax_advice", "en", ADVISOR_EN),
        ("new_credit", "de", PROMPTS["counselling_de"]),
    ],
)
async def test_answer_ends_with_the_servers_pointer(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    category: str,
    language: str,
    pointer: str,
) -> None:
    apertus.guardrails = [check(category=category, language=language)]

    reply = await ask(client=client, session=session, content="Soll ich SARON nehmen?")

    assert reply["content"] == f"{FAKE_REPLY}\n\n{pointer}"
    assert {"name": "guardrail", "passed": True, "detail": category} in reply["provenance"][
        "checks"
    ]


async def test_advisor_comes_from_the_bank_not_the_model(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.guardrails = [check(category="product_choice")]

    reply = await ask(client=client, session=session, content="ETFs or pension fund?")

    assert f"{ADVISOR_NAME}, {ADVISOR_PHONE}" in reply["content"]
    assert ADVISOR_NAME not in json.dumps(apertus.requests)


async def test_check_nested_under_the_schema_name_still_counts(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.guardrails = [json.dumps({"GuardrailCheck": json.loads(check(category="off_topic"))})]

    reply = await ask(client=client, session=session, content="Write me a poem.")

    assert reply["content"] == PROMPTS["off_topic_en"]


@pytest.mark.parametrize(("category", "language"), [("other_customer", "en"), ("off_topic", "de")])
async def test_decline_runs_no_tool_and_no_answer(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    category: str,
    language: str,
) -> None:
    apertus.guardrails = [check(category=category, language=language)]

    reply = await ask(client=client, session=session, content="Write me a poem.")

    assert reply["content"] == PROMPTS[f"{category}_{language}"]
    assert apertus.requests == []
    assert len(apertus.guardrail_requests) == 1


async def test_ok_adds_nothing(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    reply = await ask(client=client, session=session, content="How much did I spend at Migros?")

    assert reply["content"] == FAKE_REPLY
    assert len(apertus.requests) == 2


async def test_failed_check_answers_without_a_pointer(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.guardrails = ['{"category": "advice"}', '{"category": "advice"}']

    reply = await ask(client=client, session=session, content="Soll ich SARON nehmen?")

    assert reply["content"] == FAKE_REPLY
    assert {"name": "guardrail", "passed": False, "detail": "check failed"} in reply["provenance"][
        "checks"
    ]


@pytest.mark.parametrize(
    ("category", "pointer"),
    [("product_choice", f"\n\n{ADVISOR_EN}"), ("off_topic", None)],
)
async def test_streamed_reply_is_the_stored_reply(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    category: str,
    pointer: str | None,
) -> None:
    apertus.guardrails = [check(category=category)]
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}/messages"

    response = await client.post(url, params={"stream": "true"}, json={"content": "Hi"})

    events = sse_events(response=response)
    streamed = "".join(data["text"] for name, data in events if name == "token")
    stored = (await client.get(url)).json()[-1]["content"]
    assert streamed == stored
    expected = PROMPTS["off_topic_en"] if pointer is None else FAKE_REPLY + pointer
    assert stored == expected
