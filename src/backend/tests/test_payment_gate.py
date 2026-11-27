import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from app.features.payments.service import PaymentService
from app.features.payments.tools import WRITE_TOOLS, get_tools
from app.features.tool_calls import service as tool_call_service
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.dependencies import CONFIRMATIONS
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.service import NOT_ALLOWED, TOOL_FAILED, ToolCallService
from app.main import app
from tests.conftest import (
    ACCOUNTS,
    BANK_WRITES,
    CUSTOMER_TOKEN,
    TODAY,
    FakeApertus,
    fake_banking_client,
)
from tests.factories import make_conversation, make_message
from tests.sse import sse_events
from tests.test_payments_tools import WRITES, _answer, _decision, _stream

# Each payment tool with arguments the bank would take.
TOOLS = {write[0]: write[1] for write in WRITES}
CONFIRMATION = {write.name: write.confirmation for write in WRITE_TOOLS}


@pytest.fixture(autouse=True, params=["checked", "unchecked"])
def run_tool(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every case holds also when `_run_tool` passes the arguments through unchecked."""
    if request.param == "checked":
        return

    async def unchecked(
        self: ToolCallService, call_id: UUID, name: str, arguments: dict[str, Any], turn: Any
    ) -> tuple[dict[str, Any] | None, str | None]:
        tool = self.tools[name]
        assert tool.handler is not None
        output = await tool.handler(tool.args_schema.model_construct(**arguments))
        return output.model_dump(mode="json"), None

    monkeypatch.setattr(ToolCallService, "_run_tool", unchecked)


def _foreign(arguments: dict[str, Any]) -> dict[str, Any]:
    """The arguments with an id that is not the customer's."""
    ids = ("payment_id", "standing_order_id", "debit_account_id")
    field = next(field for field in ids if field in arguments)
    return {**arguments, field: "OTHER-1"}


async def _turn(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, decision: str
) -> tuple[str, list[dict[str, Any]]]:
    """A streamed turn that nobody answers; its URL and tool_call events."""
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [decision]
    response = await _stream(client=client, url=url)
    return url, [data for name, data in sse_events(response=response) if name == "tool_call"]


def test_every_write_tool_is_in_these_cases() -> None:
    assert set(TOOLS) == set(CONFIRMATION)
    for name, confirmation in CONFIRMATION.items():
        assert confirmation, name


@pytest.mark.parametrize("tool", TOOLS)
async def test_invalid_arguments_ask_nobody_and_never_write(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    url, events = await _turn(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision(tool, {**TOOLS[tool], "to": "/admin/reset"}),
    )

    assert [event["confirmation"] for event in events] == [None]
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert call["error"].startswith("Invalid arguments. to:")


@pytest.mark.parametrize("tool", TOOLS)
async def test_id_that_is_not_the_customers_never_writes(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    url, events = await _turn(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision(tool, _foreign(arguments=TOOLS[tool])),
    )

    assert [event["confirmation"] for event in events] == [None]
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert "OTHER-1 is not one of the customer's" in call["error"]


@pytest.mark.parametrize("tool", TOOLS)
async def test_turn_that_cannot_ask_never_writes(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(tool, TOOLS[tool])]

    reply = await client.post(f"{url}/messages", json={"content": "Pay my landlord."})

    assert reply.status_code == 201
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, NOT_ALLOWED)


@pytest.mark.parametrize("tool", TOOLS)
async def test_dont_allow_never_writes(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(tool, TOOLS[tool])]

    await asyncio.gather(_stream(client=client, url=url), _answer(client=client, is_allowed=False))

    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, NOT_ALLOWED)


@pytest.mark.parametrize("tool", TOOLS)
async def test_unanswered_sheet_never_writes(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
) -> None:
    monkeypatch.setattr(tool_call_service, "CONFIRMATION_TIMEOUT_SECONDS", 0.01)

    url, events = await _turn(
        client=client, session=session, apertus=apertus, decision=_decision(tool, TOOLS[tool])
    )

    assert [event["confirmation"] for event in events] == [CONFIRMATION[tool]]
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, NOT_ALLOWED)


async def _read(events: AsyncIterator[Any]) -> None:
    async for _ in events:
        pass


@pytest.mark.parametrize("tool", TOOLS)
async def test_closed_stream_never_writes(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    apertus.decisions = [_decision(tool, TOOLS[tool])]
    banking = fake_banking_client()
    payments = PaymentService(banking=banking, ledger=LedgerService(banking=banking))
    confirmations = Confirmations()
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=app.state.apertus,
        tools=get_tools(service=payments, token=CUSTOMER_TOKEN),
        today=TODAY,
        confirmations=confirmations,
    )
    events = service.stream_answer(
        conversation_id=conversation.id,
        message_id=message.id,
        messages=[{"role": "user", "content": "Pay my landlord."}],
    )
    turn = asyncio.create_task(_read(events=events))
    async with asyncio.timeout(5):
        while not confirmations.waiting:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    ((conversation_id, tool_call_id),) = confirmations.waiting

    # The server cancels the turn when the page closes its stream.
    turn.cancel()
    with pytest.raises(asyncio.CancelledError):
        await turn

    assert not confirmations.answer(
        conversation_id=conversation_id, tool_call_id=tool_call_id, is_allowed=True
    )
    assert BANK_WRITES == []
    await banking.close()


@pytest.mark.parametrize("tool", TOOLS)
async def test_tool_refused_earlier_in_the_turn_is_not_asked_again(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    first = _decision(tool, TOOLS[tool])
    second = _decision(tool, _foreign(arguments=TOOLS[tool]))
    apertus.decisions = [first, second]

    response, _ = await asyncio.gather(
        _stream(client=client, url=url), _answer(client=client, is_allowed=False)
    )

    events = [data for name, data in sse_events(response=response) if name == "tool_call"]
    assert [event["confirmation"] for event in events] == [CONFIRMATION[tool], None]
    assert BANK_WRITES == []
    calls = (await client.get(f"{url}/tool-calls")).json()
    assert [call["error"] for call in calls] == [NOT_ALLOWED, NOT_ALLOWED]


@pytest.mark.parametrize("tool", TOOLS)
async def test_one_allow_writes_once_and_a_second_allow_is_not_found(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, tool: str
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(tool, TOOLS[tool])]
    await asyncio.gather(_stream(client=client, url=url), _answer(client=client, is_allowed=True))
    (call,) = (await client.get(f"{url}/tool-calls")).json()

    again = await client.post(
        f"{url}/tool-calls/{call['id']}/confirmations", json={"is_allowed": True}
    )

    assert again.status_code == 404
    assert len(BANK_WRITES) == 1
    assert call["error"] is None


def _other_customers_bank() -> BankingClient:
    """A bank that knows every token as another customer's."""
    fake_http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(
            lambda _: httpx2.Response(
                200, json={"customer_id": "CUST-002", "today": TODAY.isoformat()}
            )
        ),
        base_url=get_settings().banking_api_url,
    )
    return BankingClient(settings=get_settings(), http_client=fake_http)


async def test_allow_with_another_customers_token_is_not_found(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision("create_payment", TOOLS["create_payment"])]

    async def answer_as_another_customer() -> int:
        async with asyncio.timeout(5):
            while not CONFIRMATIONS.waiting:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
        ((_, tool_call_id),) = CONFIRMATIONS.waiting
        own_bank, app.state.banking = app.state.banking, _other_customers_bank()
        try:
            answered = await client.post(
                f"{url}/tool-calls/{tool_call_id}/confirmations", json={"is_allowed": True}
            )
        finally:
            await app.state.banking.close()
            app.state.banking = own_bank
        await _answer(client=client, is_allowed=False)
        return answered.status_code

    _, status_code = await asyncio.gather(
        _stream(client=client, url=url), answer_as_another_customer()
    )

    assert status_code == 404
    assert BANK_WRITES == []


@pytest.mark.parametrize("tool", TOOLS)
async def test_sheet_that_fails_fails_only_its_call_and_never_writes(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
) -> None:
    # A bank row without a field the sheet reads.
    monkeypatch.delitem(ACCOUNTS[0], "name")
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(tool, TOOLS[tool])]

    response = await _stream(client=client, url=url)

    events = sse_events(response=response)
    (event,) = [data for name, data in events if name == "tool_call"]
    assert (event["confirmation"], event["lines"]) == (None, None)
    assert events[-1][0] == "done"
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["result"], call["error"]) == (None, TOOL_FAILED)
