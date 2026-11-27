import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.transaction_tags import service as tag_service
from app.main import app
from tests.conftest import FakeApertus

ACCOUNTS = [
    {"account_id": "ACC-PRIV", "type": "current", "iban": "CH06 0888 8000 0044 1002 0"},
    {"account_id": "ACC-TAX", "type": "savings", "iban": "CH14 0888 8000 0044 1113 7"},
]
CARD = {"card_id": "CARD-VISA", "type": "credit", "linked_account": "ACC-PRIV"}


def _booking(booking_id: str, amount: float, text: str, **fields: Any) -> dict[str, Any]:
    return {
        "booking_id": booking_id,
        "account_id": "ACC-PRIV",
        "booking_date": "2026-10-30",
        "amount": amount,
        "booking_text": text,
        "counterparty_name": None,
        "counterparty_iban": None,
        "transaction_type": "direct_debit",
        **fields,
    }


LUKAS_BOOKINGS = [
    _booking("BK-1", -212.1, "Einkauf", counterparty_name="Migros"),
    _booking("BK-2", -48.9, "Gartenmoebel", counterparty_name="Migros"),
    _booking("BK-3", -2100.0, "Miete November", counterparty_name="Immo AG"),
    _booking("BK-4", -950.0, "Hypothek Rate", counterparty_name="Bank", transaction_type="loan"),
    _booking("BK-5", 7412.55, "Lohn", counterparty_name="Firma AG"),
    _booking(
        "BK-6",
        -500.0,
        "Sparen",
        transaction_type="account_transfer",
        counterparty_iban="CH14 0888 8000 0044 1113 7",
    ),
    _booking("BK-7", -321.0, "Kartenabrechnung", transaction_type="card_settlement"),
]
PURCHASES = [
    {
        "card_transaction_id": "CTX-1",
        "card_id": "CARD-VISA",
        "transaction_date": "2026-10-20",
        "merchant_text": "SUSHI TOKYO",
        "merchant_name": "Sushi Tokyo",
        "original_amount": 4800,
        "original_currency": "JPY",
        "amount_chf": 29.5,
        "statement_id": "STMT-2026-10",
    }
]
LOAN_CHARGES = [{"booking_id": "BK-4", "loan_id": "LOAN-1", "type": "interest"}]
ANNA_BOOKINGS = [_booking("BK-A1", -30.0, "Einkauf", counterparty_name="Coop")]


def _bank_client(bookings_by_token: dict[str, tuple[str, list[dict[str, Any]]]]) -> BankingClient:
    """A bank with one customer per token; only the first customer has the card and the loan."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if token not in bookings_by_token:
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        customer_id, bookings = bookings_by_token[token]
        has_card = bookings is LUKAS_BOOKINGS
        path = request.url.path.removeprefix("/api")
        pages: dict[str, Any] = {
            "/customer": {"customer_id": customer_id},
            "/accounts": {"items": ACCOUNTS},
            "/loan-transactions": {"items": LOAN_CHARGES if has_card else []},
            "/bookings": {"items": bookings, "total": len(bookings)},
            "/cards": {"items": [CARD] if has_card else []},
            "/cards/CARD-VISA/statements": {
                "items": [{"statement_id": "STMT-2026-10", "status": "closed"}]
            },
            "/cards/CARD-VISA/transactions": {"items": PURCHASES, "total": len(PURCHASES)},
        }
        if path not in pages:
            return httpx2.Response(404, json={"detail": "Not found"})
        return httpx2.Response(200, json=pages[path])

    fake_http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
    )
    return BankingClient(settings=get_settings(), http_client=fake_http)


def _rows_of(request_body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    content = next(
        m["content"] for m in request_body["messages"] if m["content"].startswith("<rows>")
    )
    lines = content.split("<rows>\n")[1].split("\n</rows>")[0].splitlines()
    return {row["ref"]: row for row in map(json.loads, lines)}


def _by_keyword(request_body: dict[str, Any]) -> str:
    """A fake Apertus that sorts a row by what its text says."""
    categories = {
        "Gartenmoebel": "shopping",
        "Einkauf": "groceries",
        "Miete": "housing",
        "Sushi": "restaurants",
    }
    answers = []
    for ref, row in _rows_of(request_body=request_body).items():
        keyword = next((word for word in categories if word in json.dumps(row)), None)
        answers.append({"ref": ref, "category": categories.get(keyword or "", "other")})
    return json.dumps({"rows": answers})


@pytest.fixture
async def lukas(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(
        bookings_by_token={
            "customer-token": ("CUST-001", LUKAS_BOOKINGS),
            "anna-token": ("CUST-002", ANNA_BOOKINGS),
        }
    )
    apertus.structured_reply = _by_keyword
    return client


@pytest.fixture
async def anna(lukas: httpx2.AsyncClient) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer anna-token"},
    ) as api:
        yield api


async def _tags(api: httpx2.AsyncClient) -> dict[str, dict[str, Any]]:
    response = await api.get("/api/transaction-tags")
    assert response.status_code == 200
    return {tag["row_id"]: tag for tag in response.json()}


async def test_tags_every_spending_row_and_nothing_else(lukas: httpx2.AsyncClient) -> None:
    response = await lukas.post("/api/categorisations")

    assert response.status_code == 201
    assert response.json() == {
        "tagged_by_rule": 1,
        "tagged_by_model": 4,
        "already_tagged": 0,
        "skipped": 0,
    }
    tags = await _tags(api=lukas)
    assert {row_id: tag["category"] for row_id, tag in tags.items()} == {
        "BK-1": "groceries",
        "BK-2": "shopping",
        "BK-3": "housing",
        "BK-4": "loan_leasing",
        "CTX-1": "restaurants",
    }


async def test_loan_row_is_tagged_by_rule_and_the_rest_by_the_model(
    lukas: httpx2.AsyncClient,
) -> None:
    await lukas.post("/api/categorisations")

    tags = await _tags(api=lukas)

    assert tags["BK-4"]["category_set_by"] == "rule"
    assert tags["BK-4"]["category_model"] is None
    assert tags["BK-1"]["category_set_by"] == "model"
    assert tags["BK-1"]["category_model"] == "fake-smart"
    assert all(tag["category_confirmed"] is False for tag in tags.values())


async def test_two_rows_at_one_payee_get_different_categories(lukas: httpx2.AsyncClient) -> None:
    await lukas.post("/api/categorisations")

    tags = await _tags(api=lukas)

    assert tags["BK-1"]["category"] == "groceries"
    assert tags["BK-2"]["category"] == "shopping"


async def test_the_prompt_carries_the_row_fields_and_no_loan_row(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.post("/api/categorisations")

    (request,) = apertus.requests
    rows = _rows_of(request_body=request).values()
    assert len(rows) == 4
    assert any(
        row["original_currency"] == "JPY" and row["channel"] == "credit card" for row in rows
    )
    assert any(row["counterparty"] == "Migros" and row["weekday"] == "Friday" for row in rows)
    assert not any("Hypothek" in row["text"] for row in rows)


async def test_a_second_call_sends_no_tagged_row(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.post("/api/categorisations")
    apertus.requests.clear()

    response = await lukas.post("/api/categorisations")

    assert apertus.requests == []
    assert response.json() == {
        "tagged_by_rule": 0,
        "tagged_by_model": 0,
        "already_tagged": 5,
        "skipped": 0,
    }
    assert len(await _tags(api=lukas)) == 5


async def test_only_untagged_rows_are_sent_on_a_later_call(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.post("/api/categorisations")
    apertus.requests.clear()
    app.state.banking = _bank_client(
        bookings_by_token={
            "customer-token": (
                "CUST-001",
                [*LUKAS_BOOKINGS, _booking("BK-8", -15.0, "Einkauf", counterparty_name="Coop")],
            )
        }
    )

    await lukas.post("/api/categorisations")

    (request,) = apertus.requests
    (row,) = _rows_of(request_body=request).values()
    assert row["counterparty"] == "Coop"


async def test_unknown_ref_and_unknown_category_are_not_stored(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    def reply(request_body: dict[str, Any]) -> str:
        refs = list(_rows_of(request_body=request_body))
        answers = [
            {"ref": refs[0], "category": "groceries"},
            {"ref": refs[1], "category": "pocket money"},
            {"ref": "r99", "category": "housing"},
            {"ref": refs[0], "category": "health"},
        ]
        return json.dumps({"rows": answers})

    apertus.structured_reply = reply

    response = await lukas.post("/api/categorisations")

    assert response.json()["tagged_by_model"] == 1
    assert response.json()["skipped"] == 3
    tags = await _tags(api=lukas)
    assert {tag["category"] for tag in tags.values()} == {"groceries", "loan_leasing"}


async def test_a_categorisation_where_every_batch_failed_is_an_error(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    apertus.status = 500

    response = await lukas.post("/api/categorisations")

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_error"
    assert set(await _tags(api=lukas)) == {"BK-4"}


async def test_rows_go_to_apertus_in_batches(
    lukas: httpx2.AsyncClient, apertus: FakeApertus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tag_service, "BATCH_SIZE", 3)

    await lukas.post("/api/categorisations")

    sizes = sorted(len(_rows_of(request_body=request)) for request in apertus.requests)
    assert sizes == [1, 3]
    assert len(await _tags(api=lukas)) == 5


async def test_a_customer_lists_only_their_own_tags(
    lukas: httpx2.AsyncClient, anna: httpx2.AsyncClient
) -> None:
    await lukas.post("/api/categorisations")
    await anna.post("/api/categorisations")

    assert set(await _tags(api=lukas)) == {"BK-1", "BK-2", "BK-3", "BK-4", "CTX-1"}
    assert set(await _tags(api=anna)) == {"BK-A1"}
