import asyncio
from typing import Any

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.payments.sheet import lines
from tests.conftest import ACCOUNTS, BANK_WRITES, PAYMENTS, FakeApertus
from tests.factories import make_conversation
from tests.sse import sse_events
from tests.test_payments_tools import PAYMENT, _answer, _decision, _stream

ACCOUNTS_BY_ID = {account["account_id"]: account for account in ACCOUNTS}


async def _tool_call_events(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus, decision: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The tool_call events and the stored call of a turn; the customer refuses a sheet."""
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [decision]
    response, _ = await asyncio.gather(
        _stream(client=client, url=url), _answer(client=client, is_allowed=False)
    )
    events = [data for name, data in sse_events(response=response) if name == "tool_call"]
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    return events, call


async def test_payment_sheet_names_the_account_and_payee_in_swiss_format(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    arguments = {**PAYMENT, "amount": 1250, "execution_date": "2026-12-01"}

    (event,), _ = await _tool_call_events(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision("create_payment", arguments),
    )

    assert event["arguments"] == arguments
    assert [(line["label"], line["value"], line["detail"]) for line in event["lines"]] == [
        ("Type", "Domestic payment", None),
        ("Debit account", "Privatkonto", "CH06 0888 8000 0044 1002 0"),
        ("Payee", "Wohnbau Sihlfeld AG", None),
        ("IBAN", "CH41 0023 5000 0001 5558 2", None),
        ("Amount", "CHF 1'250.00", None),
        ("Date", "01.12.2026", None),
    ]


async def test_delete_standing_order_sheet_names_its_payee_amount_and_frequency(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    (event,), _ = await _tool_call_events(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision("delete_standing_order", {"standing_order_id": "SO-RENT"}),
    )

    shown = {line["label"]: line["value"] for line in event["lines"]}
    assert shown["Payee"] == "Wohnbau Sihlfeld AG"
    assert shown["Amount"] == "CHF 2'800.00"
    assert shown["Frequency"] == "Monthly"
    assert shown["Next payment"] == "28.11.2026"


def test_change_sheet_marks_what_changes() -> None:
    (payment,) = [row for row in PAYMENTS if row["payment_id"] == "PAY-0232"]

    shown = lines(
        values={"payment_id": "PAY-0232", "amount": 150.0, "debit_account_id": "ACC-TAX"},
        accounts=ACCOUNTS_BY_ID,
        item=payment,
    )

    by_label = {line.label: line for line in shown}
    assert (by_label["Amount"].value, by_label["Amount"].detail) == ("CHF 150.00", "Was CHF 168.25")
    assert (by_label["Debit account"].value, by_label["Debit account"].detail) == (
        "Sparkonto Steuern",
        "Was Privatkonto",
    )
    assert (by_label["Date"].value, by_label["Date"].detail) == ("15.01.2027", None)


@pytest.mark.parametrize(
    ("tool", "arguments", "hint"),
    [
        ("create_payment", {**PAYMENT, "debit_account_id": "ACC-OTHER"}, "list_accounts"),
        (
            "create_payment",
            {
                **{
                    key: value
                    for key, value in PAYMENT.items()
                    if key not in ("payee_name", "payee_iban")
                },
                "payment_type": "account_transfer",
                "credit_account_id": "ACC-OTHER",
            },
            "list_accounts",
        ),
        ("update_payment", {"payment_id": "PAY-9999", "amount": 10.0}, "list_payments"),
        ("delete_payment", {"payment_id": "PAY-0100"}, "list_payments"),
        ("delete_standing_order", {"standing_order_id": "SO-OTHER"}, "list_standing_orders"),
        (
            "update_standing_order",
            {"standing_order_id": "SO-OTHER", "amount": 10.0},
            "list_standing_orders",
        ),
    ],
)
async def test_id_that_is_not_the_customers_gets_no_sheet_and_never_reaches_the_bank(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    apertus: FakeApertus,
    tool: str,
    arguments: dict[str, Any],
    hint: str,
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    apertus.decisions = [_decision(tool, arguments)]

    response = await _stream(client=client, url=url)

    (event,) = [data for name, data in sse_events(response=response) if name == "tool_call"]
    assert (event["confirmation"], event["lines"]) == (None, None)
    assert BANK_WRITES == []
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert hint in call["error"]


async def test_web_search_sheet_shows_its_query_as_before(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    (event,), _ = await _tool_call_events(
        client=client,
        session=session,
        apertus=apertus,
        decision=_decision("search_web", {"query": "Hypothekarzins Zürich"}),
    )

    assert event["confirmation"] == "This sends the query to search engines outside the bank."
    assert (event["arguments"], event["lines"]) == ({"query": "Hypothekarzins Zürich"}, None)
