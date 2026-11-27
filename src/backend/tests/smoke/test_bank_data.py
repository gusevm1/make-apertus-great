import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.bank_data.tools import READS
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import BANKING_QUERIES, FakeApertus
from tests.factories import make_conversation


def _decision(tool: str, **arguments: object) -> str:
    request = ToolRequest(reason="Needed for the answer.", tool=tool, arguments=arguments)
    return ToolDecision(plan="Read the bank data.", calls=[request]).model_dump_json()


async def _ask(client: httpx2.AsyncClient, session: AsyncSession) -> dict:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    reply = await client.post(f"{url}/messages", json={"content": "Hi"})
    assert reply.status_code == 201
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    return call


async def test_bookings_tool_passes_the_filters_on_and_returns_the_banks_sums(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.decisions = [
        _decision(
            tool="list_bookings",
            date_from="2026-10-01",
            date_to="2026-10-31",
            text="Migros",
            direction="debit",
        )
    ]

    call = await _ask(client=client, session=session)

    assert BANKING_QUERIES[-1] == "from=2026-10-01&to=2026-10-31&q=Migros&direction=debit&limit=10"
    assert call["error"] is None
    assert (call["result"]["total"], call["result"]["sum_debit"]) == (51, -989.6)
    # Empty fields are dropped to leave room for rows.
    assert "counterparty_iban" not in call["result"]["items"][0]


async def test_an_argument_can_be_part_of_the_path(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.decisions = [_decision(tool="get_balance_preview", account_id="ACC-PRIV")]

    call = await _ask(client=client, session=session)

    assert call["result"] == {"account_id": "ACC-PRIV", "points": []}


async def test_an_id_the_bank_does_not_know_comes_back_as_an_error_to_correct(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.decisions = [_decision(tool="get_balance_preview", account_id="Privatkonto")]

    call = await _ask(client=client, session=session)

    assert call["result"] is None
    assert "The banking API refused the request" in call["error"]


async def test_an_argument_the_tool_does_not_have_is_an_error_not_a_dropped_filter(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    asked_before = len(BANKING_QUERIES)
    apertus.decisions = [_decision(tool="list_bookings", month="2026-10")]

    call = await _ask(client=client, session=session)

    assert call["result"] is None
    assert "month" in call["error"]
    assert len(BANKING_QUERIES) == asked_before


def test_no_tool_changes_the_bank() -> None:
    assert all(read.name.startswith(("get_", "list_")) for read in READS)
    assert not any("admin" in read.path or "auth" in read.path for read in READS)
