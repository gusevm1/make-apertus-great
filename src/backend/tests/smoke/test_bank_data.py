import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.bank_data.tools import READS
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import BANKING_QUERIES, FakeApertus
from tests.factories import make_conversation


def _decision(*calls: tuple[str, dict[str, object]]) -> str:
    requests = [
        ToolRequest(reason="Needed for the answer.", tool=tool, arguments=arguments)
        for tool, arguments in calls
    ]
    return ToolDecision(plan="Read the bank data.", calls=requests).model_dump_json()


async def _ask(client: httpx2.AsyncClient, session: AsyncSession) -> list[dict]:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    reply = await client.post(f"{url}/messages", json={"content": "Hi"})
    assert reply.status_code == 201
    return (await client.get(f"{url}/tool-calls")).json()


async def test_the_ledger_tools_add_up_on_the_server_and_read_the_bank_once(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    asked_before = len(BANKING_QUERIES)
    october: dict[str, object] = {"date_from": "2026-10-01", "date_to": "2026-10-31"}
    apertus.decisions = [
        _decision(
            ("search_movements", {**october, "text": "migros"}),
            ("sum_by_month", {**october, "text": ["Wohnbau"]}),
            ("sum_by_counterparty", october),
        )
    ]

    search, months, counterparties = await _ask(client=client, session=session)

    assert len(BANKING_QUERIES) == asked_before + 1
    assert (search["error"], search["result"]["count"]) == (None, 1)
    assert search["result"]["money_out_chf"] == "-212.1"
    assert search["result"]["row_ids"] == ["BK-00101"]
    assert months["result"]["months"] == [
        {
            "month": "2026-10",
            "count": 1,
            "money_out_chf": "-2800.0",
            "money_in_chf": "0",
            "provisional_out_chf": "0",
            "provisional_in_chf": "0",
        }
    ]
    names = [group["counterparty"] for group in counterparties["result"]["counterparties"]]
    assert names == ["Wohnbau Sihlfeld AG", "Migros"]


async def test_an_argument_can_be_part_of_the_path(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.decisions = [_decision(("get_balance_preview", {"account_id": "ACC-PRIV"}))]

    (call,) = await _ask(client=client, session=session)

    assert call["result"] == {"account_id": "ACC-PRIV", "points": []}


async def test_an_id_the_bank_does_not_know_comes_back_as_an_error_to_correct(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    apertus.decisions = [_decision(("get_balance_preview", {"account_id": "Privatkonto"}))]

    (call,) = await _ask(client=client, session=session)

    assert call["result"] is None
    assert "The banking API refused the request" in call["error"]


async def test_an_argument_the_tool_does_not_have_is_an_error_not_a_dropped_filter(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    asked_before = len(BANKING_QUERIES)
    apertus.decisions = [_decision(("search_movements", {"month": "2026-10"}))]

    (call,) = await _ask(client=client, session=session)

    assert call["result"] is None
    assert "month" in call["error"]
    assert len(BANKING_QUERIES) == asked_before


async def test_a_period_that_ends_before_it_starts_is_an_error_not_an_empty_month(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    asked_before = len(BANKING_QUERIES)
    apertus.decisions = [
        _decision(("sum_by_month", {"date_from": "2026-10-01", "date_to": "2026-09-30"}))
    ]

    (call,) = await _ask(client=client, session=session)

    assert "date_from is after date_to" in call["error"]
    assert len(BANKING_QUERIES) == asked_before


def test_no_tool_changes_the_bank() -> None:
    assert all(read.name.startswith(("get_", "list_")) for read in READS)
    assert not any("admin" in read.path or "auth" in read.path for read in READS)
