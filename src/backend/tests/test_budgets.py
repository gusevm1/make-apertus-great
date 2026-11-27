from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.main import app
from tests.conftest import FakeApertus
from tests.test_sum_spending import _all_but_the_garden_furniture
from tests.test_transaction_tags import ANNA_BOOKINGS, LUKAS_BOOKINGS, PURCHASES, _bank_client


@pytest.fixture
async def lukas(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(
        bookings_by_token={
            "customer-token": ("CUST-001", LUKAS_BOOKINGS),
            "anna-token": ("CUST-002", ANNA_BOOKINGS),
        }
    )
    apertus.structured_reply = _all_but_the_garden_furniture
    assert (await client.post("/api/categorisations")).status_code == 201
    apertus.structured_reply = None
    return client


@pytest.fixture
async def anna(lukas: httpx2.AsyncClient) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer anna-token"},
    ) as api:
        yield api


async def _budget(api: httpx2.AsyncClient, category: str, amount_chf: float) -> dict[str, Any]:
    response = await api.post("/api/budgets", json={"category": category, "amount_chf": amount_chf})
    assert response.status_code == 201
    return response.json()


def _lines(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {line["category"]: line for line in summary["budgets"]}


async def test_a_budget_is_set_changed_and_deleted(lukas: httpx2.AsyncClient) -> None:
    budget = await _budget(api=lukas, category="restaurants", amount_chf=300)

    changed = await lukas.patch(f"/api/budgets/{budget['id']}", json={"amount_chf": 250.5})
    assert changed.json()["amount_chf"] == 250.5
    assert [row["amount_chf"] for row in (await lukas.get("/api/budgets")).json()] == [250.5]
    assert (await lukas.delete(f"/api/budgets/{budget['id']}")).status_code == 204
    assert (await lukas.get("/api/budgets")).json() == []


async def test_a_second_budget_for_a_category_is_a_conflict(lukas: httpx2.AsyncClient) -> None:
    await _budget(api=lukas, category="restaurants", amount_chf=300)

    response = await lukas.post("/api/budgets", json={"category": "restaurants", "amount_chf": 1})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"category": "pets", "amount_chf": 100},
        {"category": "restaurants", "amount_chf": 0},
        {"category": "restaurants", "amount_chf": 100_000.01},
    ],
)
async def test_an_unknown_category_or_an_amount_out_of_range_is_refused(
    lukas: httpx2.AsyncClient, body: dict[str, Any]
) -> None:
    assert (await lukas.post("/api/budgets", json=body)).status_code == 422


async def test_another_customers_budget_is_not_found(
    lukas: httpx2.AsyncClient, anna: httpx2.AsyncClient
) -> None:
    budget = await _budget(api=lukas, category="restaurants", amount_chf=300)

    url = f"/api/budgets/{budget['id']}"
    assert (await anna.patch(url, json={"amount_chf": 1})).status_code == 404
    assert (await anna.delete(url)).status_code == 404
    assert (await anna.get("/api/budget-summaries?month=2026-10")).json()["budgets"] == []
    assert (await lukas.get("/api/budgets")).json()[0]["amount_chf"] == 300


async def test_a_closed_month_compares_each_budget_with_the_rows_it_lists(
    lukas: httpx2.AsyncClient,
) -> None:
    await _budget(api=lukas, category="restaurants", amount_chf=20)
    await _budget(api=lukas, category="groceries", amount_chf=300)
    await _budget(api=lukas, category="health", amount_chf=100)

    summary = (await lukas.get("/api/budget-summaries?month=2026-10")).json()

    amounts = {row["booking_id"]: -Decimal(str(row["amount"])) for row in LUKAS_BOOKINGS}
    amounts |= {row["card_transaction_id"]: Decimal(str(row["amount_chf"])) for row in PURCHASES}
    lines = _lines(summary=summary)
    for category, line in lines.items():
        named = sum((amounts[row_id] for row_id in summary["row_ids"][category]), Decimal(0))
        assert Decimal(line["spent_chf"]) == named
    assert [line["category"] for line in summary["budgets"]] == ["groceries", "health", "restaurants"]
    assert lines["restaurants"] == {
        "category": "restaurants",
        "budget_chf": "20.00",
        "spent_chf": "29.5",
        "left_chf": "-9.50",
        "over": True,
    }
    assert (lines["groceries"]["left_chf"], lines["groceries"]["over"]) == ("87.90", False)
    assert (lines["health"]["spent_chf"], lines["health"]["over"]) == ("0", False)
    assert summary["row_ids"]["health"] == []
    totals = {key: summary[key] for key in ("budget_chf", "spent_chf", "left_chf", "over")}
    assert totals == {
        "budget_chf": "420.00",
        "spent_chf": "241.6",
        "left_chf": "178.40",
        "over": False,
    }
    assert {line["category"]: line["spent_chf"] for line in summary["unbudgeted"]} == {
        "housing": "2100.0",
        "loan_leasing": "950.0",
        "not_categorised": "48.9",
    }
    assert (summary["days_in_month"], summary["days_elapsed"]) == (31, None)


async def test_the_month_defaults_to_todays_and_counts_its_days(
    lukas: httpx2.AsyncClient,
) -> None:
    await _budget(api=lukas, category="restaurants", amount_chf=300)

    summary = (await lukas.get("/api/budget-summaries")).json()

    assert (summary["month"], summary["days_in_month"], summary["days_elapsed"]) == (
        "2026-11",
        30,
        27,
    )
    assert _lines(summary=summary)["restaurants"]["spent_chf"] == "0"
    assert summary["unbudgeted"] == []


async def test_a_month_that_is_no_month_is_refused(lukas: httpx2.AsyncClient) -> None:
    assert (await lukas.get("/api/budget-summaries?month=2026-13")).status_code == 422


async def test_the_tool_returns_what_the_endpoint_returns(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await _budget(api=lukas, category="restaurants", amount_chf=20)
    request = ToolRequest(reason="Budgets.", tool="compare_budgets", arguments={"month": "2026-10"})
    apertus.decisions = [ToolDecision(plan="Compare.", calls=[request]).model_dump_json()]
    apertus.reply = "CHF 9.50 over."
    conversation = (await lukas.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}"

    message = await lukas.post(f"{url}/messages", json={"content": "Restaurant budget?"})

    assert message.status_code == 201
    (call,) = (await lukas.get(f"{url}/tool-calls")).json()
    endpoint = (await lukas.get("/api/budget-summaries?month=2026-10")).json()
    assert call["result"] == endpoint
