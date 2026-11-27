import json
from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.main import app
from tests.conftest import FakeApertus
from tests.sse import sse_events
from tests.test_category_certainty import _with_certainty
from tests.test_transaction_tags import LUKAS_BOOKINGS, PURCHASES, _bank_client


def _all_but_the_garden_furniture(request_body: dict[str, Any]) -> str:
    """The certainty fake, without an answer for BK-2, which so stays without a category."""
    answer = json.loads(_with_certainty(request_body=request_body))
    rows = [row for row in answer["rows"] if row["category"] != "shopping"]
    return json.dumps({"rows": rows})


@pytest.fixture
async def lukas(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(
        bookings_by_token={"customer-token": ("CUST-001", LUKAS_BOOKINGS)}
    )
    apertus.structured_reply = _all_but_the_garden_furniture
    assert (await client.post("/api/categorisations")).status_code == 201
    return client


async def _ask(
    api: httpx2.AsyncClient, apertus: FakeApertus, answer: str, **arguments: Any
) -> tuple[dict[str, Any], str]:
    """One chat turn that calls sum_spending; returns the tool's result and the stored answer."""
    request = ToolRequest(reason="Needs the sums.", tool="sum_spending", arguments=arguments)
    decision = ToolDecision(plan="Add it up.", calls=[request]).model_dump_json()
    apertus.structured_reply = None
    apertus.decisions = [decision]
    apertus.reply = answer
    conversation = (await api.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}"
    message = await api.post(f"{url}/messages", json={"content": "How much?"})
    assert message.status_code == 201
    (call,) = (await api.get(f"{url}/tool-calls")).json()
    assert call["error"] is None
    return call["result"], message.json()["content"]


def _groups(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {group["group"]: group for group in result["groups"]}


async def test_every_total_is_the_sum_of_the_rows_it_names(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    result, _ = await _ask(api=lukas, apertus=apertus, answer="Done.", group_by="category")

    amounts = {row["booking_id"]: -Decimal(str(row["amount"])) for row in LUKAS_BOOKINGS}
    amounts |= {row["card_transaction_id"]: Decimal(str(row["amount_chf"])) for row in PURCHASES}
    for name, group in _groups(result=result).items():
        named = sum((amounts[row_id] for row_id in result["row_ids"][name]), Decimal(0))
        assert Decimal(group["spent_chf"]) == named
        assert group["count"] == len(result["row_ids"][name])
    assert Decimal(result["spent_chf"]) == Decimal("3340.5")
    assert result["count"] == 5


async def test_rows_without_a_category_are_their_own_group(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    result, _ = await _ask(api=lukas, apertus=apertus, answer="Done.", group_by="category")

    groups = _groups(result=result)
    assert (groups["not_categorised"]["spent_chf"], groups["not_categorised"]["count"]) == (
        "48.9",
        1,
    )
    assert result["row_ids"]["not_categorised"] == ["BK-2"]
    # An unknown certainty counts as uncertain, a high or medium one does not.
    assert {name: group["uncertain_count"] for name, group in groups.items()} == {
        "housing": 0,
        "loan_leasing": 0,
        "groceries": 0,
        "restaurants": 1,
        "not_categorised": 0,
    }


async def test_a_figure_with_many_uncertain_bookings_gets_the_pointer(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    _, answer = await _ask(
        api=lukas,
        apertus=apertus,
        answer="You spent CHF 29.50 on restaurants.",
        group_by="category",
        language="en",
    )

    assert answer == (
        "You spent CHF 29.50 on restaurants.\n\n1 bookings in this figure may be in the wrong "
        "category. Check them in the [category center](#categories)."
    )


async def test_a_figure_without_uncertain_bookings_gets_no_pointer(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    _, answer = await _ask(
        api=lukas,
        apertus=apertus,
        answer="You spent CHF 212.10 on groceries.",
        group_by="category",
        category="groceries",
    )

    assert answer == "You spent CHF 212.10 on groceries."


async def test_the_total_counts_the_uncertain_bookings_of_all_groups(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    _, answer = await _ask(
        api=lukas, apertus=apertus, answer="Alles zusammen: CHF 3'340.50.", group_by="severity"
    )

    assert answer.endswith(
        "1 Buchungen in dieser Zahl sind vielleicht falsch kategorisiert. "
        "Prüfen Sie sie im [Kategorien-Center](#categories)."
    )


async def test_a_personal_tag_sums_its_spending_and_its_savings_apart(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    tag = (await lukas.post("/api/personal-tags", json={"name": "Japan"})).json()
    for row_id in ("CTX-1", "BK-6"):
        source = "card_transaction" if row_id.startswith("CTX") else "booking"
        response = await lukas.post(
            f"/api/personal-tags/{tag['id']}/assignments",
            json={"row_source": source, "row_id": row_id},
        )
        assert response.status_code == 201

    result, _ = await _ask(
        api=lukas, apertus=apertus, answer="Done.", group_by="personal_tag", personal_tag="japan"
    )

    assert [group["group"] for group in result["groups"]] == ["Japan"]
    (japan,) = result["groups"]
    assert (japan["spent_chf"], japan["count"], japan["saved_chf"]) == ("29.5", 1, "500.0")
    assert result["row_ids"]["Japan"] == ["CTX-1", "BK-6"]


async def test_an_unknown_personal_tag_names_the_ones_there_are(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.post("/api/personal-tags", json={"name": "Lina"})
    request = ToolRequest(
        reason="Sums.",
        tool="sum_spending",
        arguments={"group_by": "category", "personal_tag": "Mars"},
    )
    apertus.structured_reply = None
    apertus.decisions = [ToolDecision(plan="Add.", calls=[request]).model_dump_json()]
    conversation = (await lukas.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}"

    await lukas.post(f"{url}/messages", json={"content": "Mars?"})

    (call,) = (await lukas.get(f"{url}/tool-calls")).json()
    assert call["error"] == "The customer has no personal tag 'Mars'. Their tags: Lina."


async def test_a_streamed_answer_shows_the_pointer_under_the_checked_answer(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    request = ToolRequest(
        reason="Sums.", tool="sum_spending", arguments={"group_by": "category", "language": "en"}
    )
    apertus.structured_reply = None
    apertus.decisions = [ToolDecision(plan="Add it up.", calls=[request]).model_dump_json()]
    apertus.reply = "You spent CHF 29.50 on restaurants."
    conversation = (await lukas.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}"

    response = await lukas.post(
        f"{url}/messages", params={"stream": "true"}, json={"content": "Restaurants?"}
    )

    tokens = "".join(
        data["text"] for name, data in sse_events(response=response) if name == "token"
    )
    (stored,) = [m for m in (await lukas.get(f"{url}/messages")).json() if m["role"] == "assistant"]
    expected = (
        "You spent CHF 29.50 on restaurants.\n\n1 bookings in this figure may be in the wrong "
        "category. Check them in the [category center](#categories)."
    )
    assert tokens == expected
    assert stored["content"] == expected
