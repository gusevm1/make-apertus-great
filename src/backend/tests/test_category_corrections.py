from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.main import app
from tests.conftest import FakeApertus
from tests.test_transaction_tags import (
    LUKAS_BOOKINGS,
    _bank_client,
    _booking,
    _categorise_only,
    _tags,
    anna,  # noqa: F401
    lukas,  # noqa: F401
)


async def _correct(api: httpx2.AsyncClient, scope: str, key: str, category: str) -> httpx2.Response:
    return await api.post(
        "/api/category-corrections", json={"scope": scope, "key": key, "category": category}
    )


async def _summaries(api: httpx2.AsyncClient, **params: str) -> dict[str | None, dict[str, Any]]:
    response = await api.get("/api/category-summaries", params=params)
    assert response.status_code == 200
    return {summary["category"]: summary for summary in response.json()}


async def test_a_payee_correction_changes_every_row_of_the_payee_and_no_other(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    response = await _correct(api=lukas, scope="payee", key="  MIGROS ", category="groceries")

    assert response.status_code == 201
    assert response.json() == {
        "scope": "payee",
        "key": "migros",
        "category": "groceries",
        "rows_changed": 2,
    }
    tags = await _tags(api=lukas)
    for row_id in ("BK-1", "BK-2"):
        assert tags[row_id]["category"] == "groceries"
        assert tags[row_id]["category_set_by"] == "customer"
        assert tags[row_id]["category_confirmed"] is True
    assert tags["BK-3"]["category"] == "housing"
    assert tags["BK-3"]["category_set_by"] == "model"


async def test_a_payee_correction_holds_for_a_later_booking(
    lukas: httpx2.AsyncClient,  # noqa: F811
    apertus: FakeApertus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)
    await _correct(api=lukas, scope="payee", key="Migros", category="shopping")
    app.state.banking = _bank_client(
        bookings_by_token={
            "customer-token": (
                "CUST-001",
                [*LUKAS_BOOKINGS, _booking("BK-8", -9.0, "Einkauf", counterparty_name="Migros")],
            )
        }
    )
    apertus.requests.clear()

    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    assert apertus.requests == []
    assert (await _tags(api=lukas))["BK-8"]["category"] == "shopping"


async def test_a_booking_correction_changes_that_row_only(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    response = await _correct(api=lukas, scope="booking", key="booking:BK-2", category="other")

    assert response.json()["rows_changed"] == 1
    tags = await _tags(api=lukas)
    assert tags["BK-2"]["category"] == "other"
    assert tags["BK-2"]["category_confirmed"] is True
    assert tags["BK-1"]["category"] == "groceries"
    assert tags["BK-1"]["category_confirmed"] is False


async def test_confirming_keeps_the_category_and_marks_it_confirmed(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    await _correct(api=lukas, scope="booking", key="card_transaction:CTX-1", category="restaurants")

    tag = (await _tags(api=lukas))["CTX-1"]
    assert tag["category"] == "restaurants"
    assert tag["category_confirmed"] is True
    assert tag["category_certainty"] == "high"


async def test_a_correction_tags_a_row_not_categorised_yet(
    lukas: httpx2.AsyncClient,  # noqa: F811
) -> None:
    await _correct(api=lukas, scope="payee", key="Immo AG", category="housing")

    tags = await _tags(api=lukas)

    assert list(tags) == ["BK-3"]
    assert tags["BK-3"]["category_set_by"] == "customer"


async def test_another_customers_booking_is_not_found(
    lukas: httpx2.AsyncClient,  # noqa: F811
    anna: httpx2.AsyncClient,  # noqa: F811
) -> None:
    response = await _correct(api=anna, scope="booking", key="booking:BK-1", category="other")

    assert response.status_code == 404
    assert await _tags(api=lukas) == {}


async def test_an_unknown_payee_is_not_found(lukas: httpx2.AsyncClient) -> None:  # noqa: F811
    response = await _correct(api=lukas, scope="payee", key="Coop", category="groceries")

    assert response.status_code == 404


async def test_an_unknown_category_is_refused(lukas: httpx2.AsyncClient) -> None:  # noqa: F811
    response = await _correct(api=lukas, scope="payee", key="Migros", category="pocket money")

    # Checked against the customer's own categories too, so by the service, not the schema.
    assert response.status_code == 400


async def test_each_row_names_the_usual_category_of_its_payee(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.banking = _bank_client(
        bookings_by_token={
            "customer-token": (
                "CUST-001",
                [*LUKAS_BOOKINGS, _booking("BK-8", -9.0, "Einkauf", counterparty_name="Migros")],
            )
        }
    )
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    tags = await _tags(api=lukas)
    assert tags["BK-2"]["category"] == "shopping"
    assert tags["BK-2"]["payee_usual_category"] == "groceries"
    assert tags["BK-1"]["payee_usual_category"] == "groceries"
    assert tags["BK-3"]["payee_usual_category"] == "housing"

    await _correct(api=lukas, scope="payee", key="Migros", category="shopping")

    assert (await _tags(api=lukas))["BK-1"]["payee_usual_category"] == "shopping"


async def test_rows_carry_their_ledger_fields(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    tag = (await _tags(api=lukas))["BK-3"]

    assert tag["date"] == "2026-10-30"
    assert tag["text"] == "Miete November"
    assert tag["payee"] == "immo ag"
    assert Decimal(tag["amount_chf"]) == Decimal("2100")


async def test_rows_filter_by_category_and_certainty(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)
    await _correct(api=lukas, scope="booking", key="booking:BK-3", category="housing")

    by_category = await lukas.get("/api/transaction-tags", params={"category": "groceries"})
    unknown = await lukas.get("/api/transaction-tags", params={"certainty": "unknown"})
    bad = await lukas.get("/api/transaction-tags", params={"certainty": "maybe"})
    misspelt = await lukas.get("/api/transaction-tags", params={"category": "grocery"})

    assert [tag["row_id"] for tag in by_category.json()] == ["BK-1"]
    assert sorted(tag["row_id"] for tag in unknown.json()) == ["BK-1", "BK-2", "CTX-1"]
    assert bad.status_code == 422
    # Any name filters, since the customer can add categories of their own.
    assert misspelt.json() == []


async def test_summaries_add_up_the_ledger_rows_and_count_certainty(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = await _summaries(api=lukas)
    assert set(before) == {None}
    assert Decimal(before[None]["total_chf"]) == Decimal("3340.5")
    assert before[None]["row_count"] == 5

    await _categorise_only(api=lukas, monkeypatch=monkeypatch)
    await _correct(api=lukas, scope="booking", key="booking:BK-2", category="groceries")

    summaries = await _summaries(api=lukas)
    assert None not in summaries
    groceries = summaries["groceries"]
    assert Decimal(groceries["total_chf"]) == Decimal("261.0")
    assert (groceries["row_count"], groceries["unknown"], groceries["confirmed"]) == (2, 1, 1)
    assert summaries["loan_leasing"]["high"] == 1
    assert sum(Decimal(summary["total_chf"]) for summary in summaries.values()) == Decimal("3340.5")


async def test_summaries_keep_to_the_period(
    lukas: httpx2.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    october_20 = await _summaries(api=lukas, **{"from": "2026-10-01", "to": "2026-10-25"})

    assert list(october_20) == ["restaurants"]
    assert Decimal(october_20["restaurants"]["total_chf"]) == Decimal("29.5")
