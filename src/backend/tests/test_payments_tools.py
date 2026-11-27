import asyncio
from typing import Any

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.features.payments.service import Method, PaymentService
from app.features.payments.tools import WRITE_TOOLS, get_tools
from app.features.tool_calls import service as tool_call_service
from app.features.tool_calls.dependencies import CONFIRMATIONS
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.features.tool_calls.service import NOT_ALLOWED
from tests.conftest import (
    BANK_WRITES,
    COMPLETED_PAYMENT_ID,
    CUSTOMER_TOKEN,
    FakeApertus,
    fake_banking_client,
)
from tests.factories import make_conversation
from tests.sse import sse_events

RENT = {"payee_name": "Wohnbau Sihlfeld AG", "payee_iban": "CH41 0023 5000 0001 5558 2"}
PAYMENT = {
    "payment_type": "domestic",
    "debit_account_id": "ACC-PRIV",
    **RENT,
    "amount": 120.0,
    "currency": "CHF",
    "execution_date": "2026-12-01",
}
STANDING_ORDER = {
    "debit_account_id": "ACC-PRIV",
    **RENT,
    "amount": 2800.0,
    "currency": "CHF",
    "frequency": "monthly",
    "day": 28,
    "start_date": "2026-12-28",
}
# Tool, arguments, then what the bank gets and answers.
WRITES = [
    ("create_payment", PAYMENT, "POST", "/payments", PAYMENT, {"payment_id": "NEW-1", **PAYMENT}),
    (
        "update_payment",
        {"payment_id": "PAY-0232", "amount": 150.0},
        "PATCH",
        "/payments/PAY-0232",
        {"amount": 150.0},
        {"payment_id": "PAY-0232", "amount": 150.0},
    ),
    (
        "delete_payment",
        {"payment_id": "PAY-0232"},
        "DELETE",
        "/payments/PAY-0232",
        None,
        {"deleted": "/payments/PAY-0232"},
    ),
    (
        "create_standing_order",
        STANDING_ORDER,
        "POST",
        "/standing-orders",
        STANDING_ORDER,
        {"standing_order_id": "NEW-1", **STANDING_ORDER},
    ),
    (
        "update_standing_order",
        {"standing_order_id": "SO-RENT", "end_date": "2027-06-30"},
        "PATCH",
        "/standing-orders/SO-RENT",
        {"end_date": "2027-06-30"},
        {"standing_order_id": "SO-RENT", "end_date": "2027-06-30"},
    ),
    (
        "delete_standing_order",
        {"standing_order_id": "SO-RENT"},
        "DELETE",
        "/standing-orders/SO-RENT",
        None,
        {"deleted": "/standing-orders/SO-RENT"},
    ),
]


def _decision(tool: str, arguments: dict[str, Any]) -> str:
    request = ToolRequest(reason="The customer asked.", tool=tool, arguments=arguments)
    return ToolDecision(plan="Prepare it.", calls=[request]).model_dump_json()


async def _stream(client: httpx2.AsyncClient, url: str) -> httpx2.Response:
    return await client.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "Pay my landlord."}
    )


async def _answer(client: httpx2.AsyncClient, is_allowed: bool) -> None:
    """Answers the call that waits, after checking that the bank got nothing yet."""
    async with asyncio.timeout(5):
        while not CONFIRMATIONS.waiting:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    ((conversation_id, tool_call_id),) = CONFIRMATIONS.waiting
    assert BANK_WRITES == []
    answered = await client.post(
        f"/api/conversations/{conversation_id}/tool-calls/{tool_call_id}/confirmations",
        json={"is_allowed": is_allowed},
    )
    assert answered.status_code == 204


async def _allowed_turn(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, decision: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The tool_call events and the stored call of a turn whose call the customer allows."""
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [decision]
    response, _ = await asyncio.gather(
        _stream(client=client, url=url), _answer(client=client, is_allowed=True)
    )
    events = [data for name, data in sse_events(response=response) if name == "tool_call"]
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    return events, call


def test_every_tool_that_writes_to_the_bank_asks_first() -> None:
    tools = get_tools(service=PaymentService(banking=fake_banking_client()), token=CUSTOMER_TOKEN)

    assert [tool.name for tool in tools] == [write[0] for write in WRITES]
    for tool in tools:
        assert tool.confirmation, tool.name


@pytest.mark.parametrize(("tool", "arguments", "method", "path", "body", "result"), WRITES)
async def test_allowed_write_reaches_the_bank_and_stores_its_answer(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    tool: str,
    arguments: dict[str, Any],
    method: str,
    path: str,
    body: dict[str, Any] | None,
    result: dict[str, Any],
) -> None:
    (write,) = [write for write in WRITE_TOOLS if write.name == tool]

    events, call = await _allowed_turn(
        client=client, session=session, apertus=apertus, decision=_decision(tool, arguments)
    )

    assert [event["confirmation"] for event in events] == [write.confirmation]
    assert [(method, path, body)] == BANK_WRITES
    assert (call["result"], call["error"]) == (result, None)


@pytest.mark.parametrize("is_timeout", [False, True])
async def test_refused_or_unanswered_write_never_reaches_the_bank(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    monkeypatch: pytest.MonkeyPatch,
    is_timeout: bool,
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision("create_payment", PAYMENT)]

    if is_timeout:
        monkeypatch.setattr(tool_call_service, "CONFIRMATION_TIMEOUT_SECONDS", 0.01)
        await _stream(client=client, url=url)
    else:
        await asyncio.gather(
            _stream(client=client, url=url), _answer(client=client, is_allowed=False)
        )

    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, NOT_ALLOWED)


async def test_turn_without_a_stream_never_writes(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision("create_payment", PAYMENT)]

    reply = await client.post(f"{url}/messages", json={"content": "Pay my landlord."})

    assert reply.status_code == 201
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, NOT_ALLOWED)


@pytest.mark.parametrize(
    ("tool", "arguments", "error"),
    [
        ("create_payment", {**PAYMENT, "amount": -120}, "Invalid arguments. amount:"),
        ("create_payment", {**PAYMENT, "to": "/admin/reset"}, "Invalid arguments. to:"),
        ("update_payment", {"payment_id": "PAY-0232"}, "Invalid arguments. : Value error"),
        ("delete_standing_order", {}, "Invalid arguments. standing_order_id:"),
    ],
)
async def test_write_with_wrong_arguments_asks_nobody_and_never_reaches_the_bank(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    tool: str,
    arguments: dict[str, Any],
    error: str,
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(tool, arguments)]

    response = await _stream(client=client, url=url)

    events = sse_events(response=response)
    assert [data["confirmation"] for name, data in events if name == "tool_call"] == [None]
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["error"].startswith(error)


@pytest.mark.parametrize("payment_id", [".", ".."])
async def test_dot_id_never_reaches_the_bank(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, payment_id: str
) -> None:
    _, call = await _allowed_turn(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision("delete_payment", {"payment_id": payment_id}),
    )

    assert BANK_WRITES == []
    assert call["error"] == f"DELETE /payments/{payment_id} is not a change the payments allow"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/admin/reset"),
        ("POST", "/auth/login"),
        ("PATCH", "/customer"),
        ("POST", "/dashboards"),
        ("DELETE", "/payments"),
        ("PATCH", "/payments/PAY-1/../../customer"),
        ("POST", "/payments/.."),
    ],
)
async def test_write_off_the_allow_list_never_reaches_the_bank(method: Method, path: str) -> None:
    service = PaymentService(banking=fake_banking_client())

    with pytest.raises(BadRequestError):
        await service.write(method=method, path=path, token=CUSTOMER_TOKEN, body={})

    assert BANK_WRITES == []


async def test_change_to_a_completed_payment_goes_back_to_the_model(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    _, call = await _allowed_turn(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision("delete_payment", {"payment_id": COMPLETED_PAYMENT_ID}),
    )

    assert call["error"].startswith("The banking API refused the change:")
