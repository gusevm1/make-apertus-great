import json
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx2
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ledger.schemas import LedgerRow
from app.features.transaction_tags.models import PersonalTagAssignmentORM
from app.features.transaction_tags.personal_tag_service import _candidate_rows, _summary
from app.features.transaction_tags.schemas import PersonalTag, PersonalTagAssignment
from app.main import app
from tests.conftest import FakeApertus
from tests.test_transaction_tags import (
    ANNA_BOOKINGS,
    LUKAS_BOOKINGS,
    _bank_client,
)


def _input_of(request_body: dict[str, Any]) -> str:
    return next(
        message["content"]
        for message in request_body["messages"]
        if message["content"].startswith(("<accounts>\n", "<tags>\n"))
    )


def _assigned_rows(request_body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    block = _input_of(request_body=request_body).split("<rows>\n")[1].split("\n</rows>")[0]
    return {row["ref"]: row for row in map(json.loads, block.splitlines())}


def _is_inference(request_body: dict[str, Any]) -> bool:
    return "<accounts>\n" in _input_of(request_body=request_body)


def _japan_tag_reply(request_body: dict[str, Any]) -> str:
    """A fake Apertus that proposes one tag and files saving and Tokyo rows under it."""
    if _is_inference(request_body=request_body):
        tag = {"name": "Japanreise", "description": "Trip to Japan in 2027"}
        return json.dumps({"tags": [tag]})
    answers = []
    for ref, row in _assigned_rows(request_body=request_body).items():
        is_japan = "Sparen" in row["text"] or "TOKYO" in row["text"]
        answers.append({"ref": ref, "tags": ["japanreise"] if is_japan else []})
    return json.dumps({"rows": answers})


@pytest.fixture
async def lukas(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(
        bookings_by_token={
            "customer-token": ("CUST-001", LUKAS_BOOKINGS),
            "anna-token": ("CUST-002", ANNA_BOOKINGS),
        }
    )
    apertus.reply = _japan_tag_reply
    return client


@pytest.fixture
async def anna(lukas: httpx2.AsyncClient) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer anna-token"},
    ) as api:
        yield api


async def _infer(api: httpx2.AsyncClient) -> list[dict[str, Any]]:
    response = await api.post("/api/personal-tag-inferences")
    assert response.status_code == 201
    return response.json()


async def _assignments(api: httpx2.AsyncClient, tag_id: str) -> dict[str, dict[str, Any]]:
    response = await api.get(f"/api/personal-tags/{tag_id}/assignments")
    assert response.status_code == 200
    return {item["row_id"]: item for item in response.json()}


async def _create_tag(api: httpx2.AsyncClient, name: str = "Garten") -> dict[str, Any]:
    response = await api.post("/api/personal-tags", json={"name": name, "description": "Mine"})
    assert response.status_code == 201
    return response.json()


async def test_inferred_tag_and_assignments_are_stored_unconfirmed_with_the_model(
    lukas: httpx2.AsyncClient,
) -> None:
    (tag,) = await _infer(api=lukas)

    assert tag["name"] == "Japanreise"
    assert tag["description"] == "Trip to Japan in 2027"
    assert tag["set_by"] == "model"
    assert tag["model"] == "fake-smart"
    assert tag["confirmed"] is False
    assignments = await _assignments(api=lukas, tag_id=tag["id"])
    assert {row_id: item["kind"] for row_id, item in assignments.items()} == {
        "BK-6": "own_transfer",
        "CTX-1": "spending",
    }
    assert all(
        item["set_by"] == "model" and item["model"] == "fake-smart" and item["confirmed"] is False
        for item in assignments.values()
    )


async def test_spending_and_own_transfers_are_reported_apart(lukas: httpx2.AsyncClient) -> None:
    await _infer(api=lukas)

    (tag,) = (await lukas.get("/api/personal-tags")).json()

    assert Decimal(tag["spending_total_chf"]) == Decimal("29.5")
    assert tag["spending_count"] == 1
    assert Decimal(tag["own_transfer_total_chf"]) == Decimal("500")
    assert tag["own_transfer_count"] == 1


async def test_the_prompts_carry_the_goal_hints_and_only_the_candidate_rows(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await _infer(api=lukas)

    inference, assignment = apertus.requests
    text = _input_of(request_body=inference)
    assert "Sparkonto Langfristig" in text
    assert "Sparen langfristig / Japanreise" in text
    assert "Immo AG: Miete" not in text
    rows = _assigned_rows(request_body=assignment)
    assert sorted(row["text"] for row in rows.values()) == ["SUSHI TOKYO", "Sparen"]
    assert "<tags>\nJapanreise: Trip to Japan in 2027\n</tags>" in _input_of(
        request_body=assignment
    )


async def test_unknown_refs_and_unknown_tag_names_are_not_stored(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    def reply(request_body: dict[str, Any]) -> str:
        if _is_inference(request_body=request_body):
            return _japan_tag_reply(request_body=request_body)
        refs = list(_assigned_rows(request_body=request_body))
        answers = [
            {"ref": refs[0], "tags": ["Weltreise", "JAPANREISE"]},
            {"ref": "r99", "tags": ["Japanreise"]},
            {"ref": refs[0], "tags": []},
        ]
        return json.dumps({"rows": answers})

    apertus.reply = reply

    (tag,) = await _infer(api=lukas)

    assert len(await _assignments(api=lukas, tag_id=tag["id"])) == 1


async def test_at_most_ten_tags_are_inferred_and_names_are_cut_and_deduplicated(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    def reply(request_body: dict[str, Any]) -> str:
        if not _is_inference(request_body=request_body):
            return json.dumps({"rows": []})
        names = ["Tag", "tag", " ", *[f"Tag {number}" for number in range(12)]]
        return json.dumps({"tags": [{"name": name, "description": "A\nB"} for name in names]})

    apertus.reply = reply

    tags = await _infer(api=lukas)

    assert len(tags) == 10
    assert sorted(tag["name"] for tag in tags)[:2] == ["Tag", "Tag 0"]
    assert all(tag["description"] == "A B" for tag in tags)


async def test_a_second_run_sends_nothing_and_stores_nothing_new(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    first = await _infer(api=lukas)
    apertus.requests.clear()

    second = await _infer(api=lukas)

    assert apertus.requests == []
    assert second == first


async def test_rows_judged_without_a_tag_are_not_sent_again_but_new_rows_are(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    def reply(request_body: dict[str, Any]) -> str:
        if _is_inference(request_body=request_body):
            return _japan_tag_reply(request_body=request_body)
        refs = _assigned_rows(request_body=request_body)
        return json.dumps({"rows": [{"ref": ref, "tags": []} for ref in refs]})

    apertus.reply = reply
    await _infer(api=lukas)
    apertus.requests.clear()
    new_transfer = {
        "booking_id": "BK-9",
        "account_id": "ACC-PRIV",
        "booking_date": "2026-11-26",
        "amount": -100.0,
        "booking_text": "Sparen neu",
        "counterparty_name": None,
        "counterparty_iban": "CH14 0888 8000 0044 1113 7",
        "transaction_type": "account_transfer",
    }
    app.state.banking = _bank_client(
        bookings_by_token={"customer-token": ("CUST-001", [*LUKAS_BOOKINGS[:7], new_transfer])}
    )

    await _infer(api=lukas)

    (request,) = apertus.requests
    assert [row["text"] for row in _assigned_rows(request_body=request).values()] == ["Sparen neu"]


async def test_a_failed_batch_leaves_its_rows_for_the_next_run(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    def failing(request_body: dict[str, Any]) -> str:
        if _is_inference(request_body=request_body):
            return _japan_tag_reply(request_body=request_body)
        return "not json"

    apertus.reply = failing
    response = await lukas.post("/api/personal-tag-inferences")
    assert response.status_code == 502
    apertus.reply = _japan_tag_reply
    apertus.requests.clear()

    (tag,) = await _infer(api=lukas)

    assert len(apertus.requests) == 1
    assert len(await _assignments(api=lukas, tag_id=tag["id"])) == 2


async def test_a_customer_can_create_rename_and_describe_a_tag(lukas: httpx2.AsyncClient) -> None:
    tag = await _create_tag(api=lukas)

    assert tag["set_by"] == "customer"
    assert tag["model"] is None
    assert tag["confirmed"] is True
    response = await lukas.patch(
        f"/api/personal-tags/{tag['id']}", json={"name": "Garten neu", "description": "Neu"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Garten neu"
    assert response.json()["description"] == "Neu"
    assert (
        await lukas.patch(f"/api/personal-tags/{tag['id']}", json={"name": None})
    ).status_code == 422


async def test_a_name_the_customer_has_already_is_refused_in_any_case(
    lukas: httpx2.AsyncClient,
) -> None:
    await _create_tag(api=lukas, name="Garten")
    other = await _create_tag(api=lukas, name="Urlaub")

    created = await lukas.post("/api/personal-tags", json={"name": "GARTEN"})
    renamed = await lukas.patch(f"/api/personal-tags/{other['id']}", json={"name": "garten"})

    assert created.status_code == 409
    assert renamed.status_code == 409
    assert len((await lukas.get("/api/personal-tags")).json()) == 2


async def test_spending_and_own_transfer_rows_can_be_assigned(lukas: httpx2.AsyncClient) -> None:
    tag = await _create_tag(api=lukas)

    first = await lukas.post(
        f"/api/personal-tags/{tag['id']}/assignments",
        json={"row_source": "booking", "row_id": "BK-2"},
    )
    second = await lukas.post(
        f"/api/personal-tags/{tag['id']}/assignments",
        json={"row_source": "booking", "row_id": "BK-6"},
    )

    assert first.status_code == 201
    assert first.json()["set_by"] == "customer"
    assert first.json()["confirmed"] is True
    assert second.status_code == 201
    (listed,) = (await lukas.get("/api/personal-tags")).json()
    assert Decimal(listed["spending_total_chf"]) == Decimal("48.9")
    assert Decimal(listed["own_transfer_total_chf"]) == Decimal("500")


@pytest.mark.parametrize(
    ("row_source", "row_id"),
    [
        ("booking", "BK-5"),
        ("booking", "BK-7"),
        ("booking", "BK-404"),
        ("booking", "BK-A1"),
        ("card_transaction", "BK-1"),
    ],
)
async def test_other_rows_and_unknown_or_foreign_ids_are_not_stored(
    lukas: httpx2.AsyncClient, row_source: str, row_id: str
) -> None:
    tag = await _create_tag(api=lukas)

    response = await lukas.post(
        f"/api/personal-tags/{tag['id']}/assignments",
        json={"row_source": row_source, "row_id": row_id},
    )

    assert response.status_code == 404
    assert await _assignments(api=lukas, tag_id=tag["id"]) == {}


async def test_assigning_a_row_twice_is_a_conflict_and_one_row_can_carry_several_tags(
    lukas: httpx2.AsyncClient,
) -> None:
    first = await _create_tag(api=lukas, name="Garten")
    second = await _create_tag(api=lukas, name="Haus")
    body = {"row_source": "booking", "row_id": "BK-2"}

    assert (
        await lukas.post(f"/api/personal-tags/{first['id']}/assignments", json=body)
    ).status_code == 201
    assert (
        await lukas.post(f"/api/personal-tags/{first['id']}/assignments", json=body)
    ).status_code == 409
    assert (
        await lukas.post(f"/api/personal-tags/{second['id']}/assignments", json=body)
    ).status_code == 201


async def test_an_assignment_can_be_removed(lukas: httpx2.AsyncClient) -> None:
    tag = await _create_tag(api=lukas)
    other = await _create_tag(api=lukas, name="Haus")
    body = {"row_source": "booking", "row_id": "BK-2"}
    created = (await lukas.post(f"/api/personal-tags/{tag['id']}/assignments", json=body)).json()

    wrong_tag = await lukas.delete(f"/api/personal-tags/{other['id']}/assignments/{created['id']}")
    deleted = await lukas.delete(f"/api/personal-tags/{tag['id']}/assignments/{created['id']}")

    assert wrong_tag.status_code == 404
    assert deleted.status_code == 204
    assert await _assignments(api=lukas, tag_id=tag["id"]) == {}


async def test_deleting_a_tag_removes_its_assignments(
    lukas: httpx2.AsyncClient, session: AsyncSession
) -> None:
    (tag,) = await _infer(api=lukas)

    response = await lukas.delete(f"/api/personal-tags/{tag['id']}")

    assert response.status_code == 204
    assert (await lukas.get("/api/personal-tags")).json() == []
    count = await session.scalar(select(func.count()).select_from(PersonalTagAssignmentORM))
    assert count == 0


async def test_a_deleted_tag_is_not_inferred_again(
    lukas: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    (tag,) = await _infer(api=lukas)
    await lukas.delete(f"/api/personal-tags/{tag['id']}")
    apertus.requests.clear()

    assert await _infer(api=lukas) == []
    assert apertus.requests == []


async def test_customers_see_and_change_only_their_own_tags(
    lukas: httpx2.AsyncClient, anna: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    (tag,) = await _infer(api=lukas)
    path = f"/api/personal-tags/{tag['id']}"

    assert (await anna.get("/api/personal-tags")).json() == []
    assert (await anna.get(f"{path}/assignments")).status_code == 404
    assert (await anna.patch(path, json={"name": "Mein"})).status_code == 404
    assert (await anna.delete(path)).status_code == 404
    body = {"row_source": "booking", "row_id": "BK-A1"}
    assert (await anna.post(f"{path}/assignments", json=body)).status_code == 404
    apertus.requests.clear()
    (annas_tag,) = await _infer(api=anna)
    assert annas_tag["id"] != tag["id"]
    assert annas_tag["spending_count"] == annas_tag["own_transfer_count"] == 0
    assert len(await _assignments(api=lukas, tag_id=tag["id"])) == 2
    assert len((await lukas.get("/api/personal-tags")).json()) == 1


def _row(row_id: str, kind: str, amount: str, **fields: Any) -> LedgerRow:
    return LedgerRow.model_validate(
        {
            "source": "booking",
            "id": row_id,
            "account_id": "ACC-PRIV",
            "date": date(2026, 10, 1),
            "amount_chf": Decimal(amount),
            "text": "Text",
            "kind": kind,
            **fields,
        }
    )


def test_only_the_outgoing_leg_of_an_own_transfer_counts_toward_the_total() -> None:
    now = date(2026, 10, 1)
    tag = PersonalTag.model_validate(
        dict(
            id=UUID(int=1),
            owner_id=UUID(int=2),
            name="Japan",
            description="",
            set_by="model",
            model=None,
            confirmed=False,
            created_at=now,
            updated_at=now,
        )  # fmt: skip
    )
    rows = [
        _row("OUT", "own_transfer", "-500"),
        _row("IN", "own_transfer", "500"),
        _row("FOOD", "spending", "-20.5"),
    ]
    assignments = [
        PersonalTagAssignment.model_validate(
            dict(
                id=UUID(int=number + 10),
                tag_id=tag.id,
                owner_id=tag.owner_id,
                row_source="booking",
                row_id=row.id,
                set_by="model",
                model=None,
                confirmed=False,
                created_at=now,
            )  # fmt: skip
        )
        for number, row in enumerate(rows)
    ]

    summary = _summary(
        tag=tag, assignments=assignments, rows={(row.source, row.id): row for row in rows}
    )

    assert summary.own_transfer_total_chf == Decimal("500")
    assert summary.own_transfer_count == 1
    assert summary.spending_total_chf == Decimal("20.5")


def test_candidates_are_outgoing_own_transfers_and_spending_that_could_relate_to_a_tag() -> None:
    now = date(2026, 10, 1)
    tag = PersonalTag.model_validate(
        dict(
            id=UUID(int=1),
            owner_id=UUID(int=2),
            name="Lina",
            description="",
            set_by="model",
            model=None,
            confirmed=False,
            created_at=now,
            updated_at=now,
        )  # fmt: skip
    )
    rows = [
        _row("TRANSFER", "own_transfer", "-100"),
        _row("INCOMING-LEG", "own_transfer", "100"),
        _row("NAME", "spending", "-5", text="Schwimmkurs Lina"),
        _row("CURRENCY", "spending", "-5", original_currency="JPY"),
        _row("CATEGORY", "spending", "-5"),
        _row("OTHER", "spending", "-5"),
        _row("CREDIT", "credit", "5", text="Unterhalt Lina"),
    ]

    candidates = _candidate_rows(
        rows=rows, categories={("booking", "CATEGORY"): "children"}, tags=[tag]
    )

    assert [row.id for row in candidates] == ["TRANSFER", "NAME", "CURRENCY", "CATEGORY"]
