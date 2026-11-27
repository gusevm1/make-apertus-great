from typing import Any

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import BANK_WRITES, FakeApertus
from tests.factories import make_conversation
from tests.sse import sse_events
from tests.test_payments_tools import PAYMENT, _allowed_turn, _decision, _stream

UPDATE = {"standing_order_id": "SO-RENT"}


@pytest.mark.parametrize(
    ("tool", "arguments", "error"),
    [
        (
            "create_payment",
            {**PAYMENT, "payee_iban": "CH94 0076 2011 6238 5295 7"},
            "Invalid arguments. payee_iban: Value error, Not a valid IBAN",
        ),
        (
            "create_payment",
            {**PAYMENT, "payee_iban": "CH93-0076-2011-6238-5295-7"},
            "Invalid arguments. payee_iban: Value error, Not a valid IBAN",
        ),
        (
            "create_payment",
            {**PAYMENT, "payee_name": "A" * 71},
            "Invalid arguments. payee_name: String should have at most 70 characters",
        ),
        (
            "create_payment",
            {**PAYMENT, "reference": "1" * 36},
            "Invalid arguments. reference: String should have at most 35 characters",
        ),
        (
            "create_payment",
            {**PAYMENT, "amount": 12.345},
            "Invalid arguments. amount: Value error, Send the amount with at most two decimals",
        ),
        (
            "update_standing_order",
            {**UPDATE, "amount": 0.001},
            "Invalid arguments. amount: Value error, Send the amount with at most two decimals",
        ),
        ("update_standing_order", {**UPDATE, "end_date": "never"}, "Invalid arguments. end_date"),
    ],
)
async def test_argument_the_bank_cannot_take_gets_no_sheet_and_no_write(
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


@pytest.mark.parametrize(
    ("tool", "arguments", "body"),
    [
        (
            "create_payment",
            {**PAYMENT, "payee_iban": "CH93 0076 2011 6238 5295 7", "amount": 12.35},
            {**PAYMENT, "payee_iban": "CH93 0076 2011 6238 5295 7", "amount": 12.35},
        ),
        (
            "create_payment",
            {**PAYMENT, "payee_iban": "CH9300762011623852957", "payee_name": "A" * 70},
            {**PAYMENT, "payee_iban": "CH9300762011623852957", "payee_name": "A" * 70},
        ),
        (
            "update_standing_order",
            {**UPDATE, "end_date": "none"},
            {"end_date": None},
        ),
        (
            "update_payment",
            {"payment_id": "PAY-0232", "payee_name": None, "amount": 150.0},
            {"amount": 150.0},
        ),
        (
            "update_standing_order",
            {**UPDATE, "payee_iban": None, "end_date": None, "day": 1},
            {"day": 1},
        ),
    ],
)
async def test_allowed_write_sends_the_bank_only_what_the_customer_saw(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    tool: str,
    arguments: dict[str, Any],
    body: dict[str, Any],
) -> None:
    events, call = await _allowed_turn(
        client=client, session=session, apertus=apertus, decision=_decision(tool, arguments)
    )

    assert events[0]["arguments"] == arguments
    assert call["error"] is None
    ((_, _, sent),) = BANK_WRITES
    assert sent == body
