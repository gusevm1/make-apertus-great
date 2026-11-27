import json
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.schemas import LedgerRow
from app.features.transaction_tags import service as tag_service
from app.features.transaction_tags.schemas import CATEGORIES
from app.features.transaction_tags.severity import effective_severity, payee_key
from app.main import app
from tests.conftest import FakeApertus

ACCOUNTS = [
    {
        "account_id": "ACC-PRIV",
        "name": "Privatkonto",
        "type": "current",
        "iban": "CH06 0888 8000 0044 1002 0",
    },
    {
        "account_id": "ACC-TAX",
        "name": "Sparkonto Langfristig",
        "type": "savings",
        "iban": "CH14 0888 8000 0044 1113 7",
    },
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
STANDING_ORDERS = [
    {
        "standing_order_id": "SO-LT",
        "payee_name": "Sparkonto Langfristig",
        "credit_account_id": "ACC-TAX",
        "message": "Sparen langfristig / Japanreise",
        "amount": 500.0,
        "frequency": "monthly",
    },
    {
        "standing_order_id": "SO-RENT",
        "payee_name": "Immo AG",
        "credit_account_id": None,
        "message": "Miete",
        "amount": 2100.0,
        "frequency": "monthly",
    },
]
LOAN_CHARGES = [{"booking_id": "BK-4", "loan_id": "LOAN-1", "type": "interest"}]
ANNA_BOOKINGS = [_booking("BK-A1", -30.0, "Einkauf", counterparty_name="Coop")]


def _bank_client(bookings_by_token: dict[str, tuple[str, list[dict[str, Any]]]]) -> BankingClient:
    """A bank with one customer per token; only the first customer has the card and the loan."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/system/info":
            return httpx2.Response(200, json={"today": "2026-11-27"})
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if token not in bookings_by_token:
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        customer_id, bookings = bookings_by_token[token]
        has_card = bookings is LUKAS_BOOKINGS
        path = request.url.path.removeprefix("/api")
        pages: dict[str, Any] = {
            "/customer": {"customer_id": customer_id},
            "/accounts": {"items": ACCOUNTS},
            "/standing-orders": {"items": STANDING_ORDERS if has_card else []},
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
    if any("<categories>\n" in message["content"] for message in request_body["messages"]):
        return _severity_reply(request_body=request_body)
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


SEVERITIES = {
    "housing": "critical",
    "groceries": "critical",
    "restaurants": "minor",
    "leisure_travel": "major",
}


def _severity_input(request_body: dict[str, Any]) -> str:
    return next(m["content"] for m in request_body["messages"] if "<categories>\n" in m["content"])


def _asked_categories(request_body: dict[str, Any]) -> list[str]:
    content = _severity_input(request_body=request_body)
    return content.split("<categories>\n")[1].split("\n</categories>")[0].splitlines()


def _severity_reply(request_body: dict[str, Any]) -> str:
    """A fake Apertus that rates the asked categories from `SEVERITIES`, else moderate."""
    return json.dumps(
        {
            "categories": [
                {
                    "category": category,
                    "severity": SEVERITIES.get(category, "moderate"),
                    "reason": f"Reason for {category}",
                }
                for category in _asked_categories(request_body=request_body)
            ]
        }
    )


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
        "tagged_by_correction": 0,
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
        "tagged_by_correction": 0,
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


def _migros(row_id: str, text: str = "Einkauf") -> dict[str, Any]:
    return _booking(row_id, -15.0, text, counterparty_name="  MIGROS ")


def test_payee_is_the_counterparty_else_the_text_in_one_spelling() -> None:
    row = LedgerRow(
        source="booking",
        id="BK-1",
        account_id="ACC-PRIV",
        date=date(2026, 10, 30),
        amount_chf=Decimal(-5),
        text="  Kiosk   am Bahnhof",
        kind="spending",
    )

    assert payee_key(row=row) == "kiosk am bahnhof"
    assert payee_key(row=row.model_copy(update={"counterparty": " Net  Flix "})) == "net flix"


def test_a_booking_override_beats_a_payee_override_beats_the_category_beats_the_default() -> None:
    stored = {
        ("booking", "booking:BK-1"): "negligible",
        ("payee", "migros"): "major",
        ("category", "groceries"): "moderate",
    }

    def severity(booking: str, payee: str | None, category: str = "groceries") -> tuple[str, str]:
        return effective_severity(category=category, booking=booking, payee=payee, stored=stored)

    assert severity("booking:BK-1", "migros") == ("negligible", "booking")
    assert severity("booking:BK-2", "migros") == ("major", "payee")
    assert severity("booking:BK-2", "coop") == ("moderate", "category")
    assert severity("booking:BK-2", None) == ("moderate", "category")
    assert severity("booking:BK-2", "coop", category="housing") == ("critical", "default")


async def test_a_row_without_a_setting_has_the_default_severity(lukas: httpx2.AsyncClient) -> None:
    await lukas.post("/api/categorisations")

    tags = await _tags(api=lukas)

    assert (tags["BK-3"]["severity"], tags["BK-3"]["severity_source"]) == ("critical", "default")
    assert (tags["BK-2"]["severity"], tags["BK-2"]["severity_source"]) == ("moderate", "default")


async def test_the_proposal_stores_one_unconfirmed_severity_per_category(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.post("/api/categorisations")
    apertus.requests.clear()

    response = await lukas.post("/api/severity-proposals")

    assert response.status_code == 201
    settings = {setting["key"]: setting for setting in response.json()}
    assert set(settings) == set(CATEGORIES)
    assert settings["housing"]["severity"] == "critical"
    assert settings["restaurants"]["severity"] == "minor"
    assert settings["restaurants"]["reason"] == "Reason for restaurants"
    assert all(
        setting["scope"] == "category"
        and setting["set_by"] == "model"
        and setting["model"] == "fake-smart"
        and setting["confirmed"] is False
        for setting in settings.values()
    )
    (request,) = apertus.requests
    prompt = _severity_input(request_body=request)
    assert "Sparkonto Langfristig" in prompt
    assert "Sparen langfristig / Japanreise" in prompt
    assert "Miete" not in prompt
    assert "groceries: 212.1" in prompt
    assert "restaurants: 29.5" in prompt
    assert "shopping: 48.9" in prompt
    listed = (await lukas.get("/api/severity-settings")).json()
    assert {setting["key"] for setting in listed} == set(CATEGORIES)


async def test_a_severity_outside_the_five_or_for_an_unknown_category_is_dropped(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    def reply(request_body: dict[str, Any]) -> str:
        answers = [
            {"category": "housing", "severity": "critical", "reason": "Rent"},
            {"category": "groceries", "severity": "vital", "reason": "Food"},
            {"category": "pocket money", "severity": "minor", "reason": "Fun"},
            {"category": "housing", "severity": "minor", "reason": "Again"},
        ]
        return json.dumps({"categories": answers})

    apertus.structured_reply = reply

    response = await lukas.post("/api/severity-proposals")

    assert [(setting["key"], setting["severity"]) for setting in response.json()] == [
        ("housing", "critical")
    ]


async def test_a_proposal_is_not_repeated_once_stored(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.post("/api/severity-proposals")
    apertus.requests.clear()

    response = await lukas.post("/api/severity-proposals")

    assert apertus.requests == []
    assert len(response.json()) == len(CATEGORIES)


async def test_a_proposal_only_asks_for_categories_without_a_setting(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await lukas.patch(
        "/api/severity-settings",
        json={"scope": "category", "key": "leisure_travel", "severity": "major"},
    )

    response = await lukas.post("/api/severity-proposals")

    (request,) = apertus.requests
    assert "leisure_travel" not in _asked_categories(request_body=request)
    customer_setting = next(s for s in response.json() if s["key"] == "leisure_travel")
    assert (customer_setting["set_by"], customer_setting["confirmed"]) == ("customer", True)


async def test_a_customer_category_setting_beats_the_default(lukas: httpx2.AsyncClient) -> None:
    await lukas.post("/api/categorisations")
    await lukas.patch(
        "/api/severity-settings",
        json={"scope": "category", "key": "restaurants", "severity": "major"},
    )

    tags = await _tags(api=lukas)

    assert (tags["CTX-1"]["severity"], tags["CTX-1"]["severity_source"]) == ("major", "category")
    assert tags["BK-3"]["severity_source"] == "default"


async def test_a_payee_override_applies_to_rows_tagged_after_it(
    lukas: httpx2.AsyncClient,
) -> None:
    await lukas.post("/api/categorisations")
    await lukas.patch(
        "/api/severity-settings",
        json={"scope": "payee", "key": "Migros", "severity": "negligible"},
    )
    app.state.banking = _bank_client(
        bookings_by_token={"customer-token": ("CUST-001", [*LUKAS_BOOKINGS, _migros("BK-8")])}
    )
    await lukas.post("/api/categorisations")

    tags = await _tags(api=lukas)

    for row_id in ("BK-1", "BK-2", "BK-8"):
        assert (tags[row_id]["severity"], tags[row_id]["severity_source"]) == (
            "negligible",
            "payee",
        )
    assert tags["BK-3"]["severity_source"] == "default"


async def test_a_booking_override_beats_the_payee_override_over_the_api(
    lukas: httpx2.AsyncClient,
) -> None:
    await lukas.post("/api/categorisations")
    for scope, key, severity in [
        ("category", "groceries", "moderate"),
        ("payee", "migros", "negligible"),
        ("booking", "booking:BK-1", "critical"),
    ]:
        response = await lukas.patch(
            "/api/severity-settings", json={"scope": scope, "key": key, "severity": severity}
        )
        assert response.status_code == 200

    tags = await _tags(api=lukas)

    assert (tags["BK-1"]["severity"], tags["BK-1"]["severity_source"]) == ("critical", "booking")
    assert (tags["BK-2"]["severity"], tags["BK-2"]["severity_source"]) == ("negligible", "payee")


async def test_setting_the_same_key_twice_replaces_the_value(lukas: httpx2.AsyncClient) -> None:
    body = {"scope": "payee", "key": "migros", "severity": "minor"}
    await lukas.patch("/api/severity-settings", json=body)
    await lukas.patch("/api/severity-settings", json=body | {"severity": "major"})

    settings = (await lukas.get("/api/severity-settings")).json()

    assert [
        (setting["key"], setting["severity"], setting["confirmed"]) for setting in settings
    ] == [("migros", "major", True)]


async def test_an_override_for_an_unknown_category_or_a_foreign_booking_is_refused(
    lukas: httpx2.AsyncClient,
) -> None:
    unknown_category = {"scope": "category", "key": "pocket money", "severity": "minor"}
    foreign_booking = {"scope": "booking", "key": "booking:BK-A1", "severity": "minor"}
    not_spending = {"scope": "booking", "key": "booking:BK-5", "severity": "minor"}
    bad_severity = {"scope": "payee", "key": "migros", "severity": "vital"}

    responses = [
        await lukas.patch("/api/severity-settings", json=body)
        for body in (unknown_category, foreign_booking, not_spending, bad_severity)
    ]

    assert [response.status_code for response in responses] == [400, 404, 404, 422]
    assert responses[0].json()["error"] == "bad_request"
    assert responses[1].json()["error"] == "not_found"
    assert (await lukas.get("/api/severity-settings")).json() == []


async def test_a_customer_sees_and_changes_only_their_own_severities(
    lukas: httpx2.AsyncClient, anna: httpx2.AsyncClient
) -> None:
    await lukas.post("/api/categorisations")
    await anna.post("/api/categorisations")
    await lukas.patch(
        "/api/severity-settings", json={"scope": "payee", "key": "coop", "severity": "critical"}
    )

    anna_settings = (await anna.get("/api/severity-settings")).json()
    anna_tags = await _tags(api=anna)

    assert anna_settings == []
    assert anna_tags["BK-A1"]["severity_source"] == "default"
