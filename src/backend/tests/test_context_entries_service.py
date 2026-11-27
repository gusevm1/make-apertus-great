from uuid import uuid4

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.context_entries.repository import ContextEntryRepository
from app.features.context_entries.schemas import ACTIVE_ENTRIES_MAX
from tests.factories import DEMO_USER_ID

GOAL = {"kind": "goal", "text": "Save for a car", "amount_chf": 20000, "target_date": "2027-06-30"}


async def test_post_stores_an_active_customer_goal(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/context-entries", json=GOAL)

    assert response.status_code == 201
    entry = response.json()
    assert entry["status"] == "active"
    assert entry["source"] == "customer"
    assert entry["amount_chf"] == 20000
    assert entry["target_date"] == "2027-06-30"
    listed = (await client.get("/api/context-entries")).json()
    assert [item["id"] for item in listed] == [entry["id"]]


async def test_patch_stores_a_new_entry_and_keeps_the_old_one_replaced(
    client: httpx2.AsyncClient,
) -> None:
    old = (await client.post("/api/context-entries", json=GOAL)).json()

    response = await client.patch(f"/api/context-entries/{old['id']}", json={"amount_chf": 25000})

    assert response.status_code == 200
    new = response.json()
    assert new["id"] != old["id"]
    assert (new["status"], new["amount_chf"], new["text"]) == ("active", 25000, GOAL["text"])
    active = (await client.get("/api/context-entries")).json()
    assert [item["id"] for item in active] == [new["id"]]
    replaced = (await client.get("/api/context-entries", params={"status": "replaced"})).json()
    assert [(item["id"], item["replaced_by_id"]) for item in replaced] == [(old["id"], new["id"])]
    assert replaced[0]["amount_chf"] == 20000


async def test_patch_on_a_replaced_entry_answers_409(client: httpx2.AsyncClient) -> None:
    old = (await client.post("/api/context-entries", json=GOAL)).json()
    await client.patch(f"/api/context-entries/{old['id']}", json={"text": "Save for a bike"})

    response = await client.patch(f"/api/context-entries/{old['id']}", json={"text": "Again"})

    assert response.status_code == 409


async def test_delete_removes_the_entry_and_its_earlier_versions(
    client: httpx2.AsyncClient,
) -> None:
    first = (await client.post("/api/context-entries", json=GOAL)).json()
    second = (await client.patch(f"/api/context-entries/{first['id']}", json={"text": "B"})).json()
    third = (await client.patch(f"/api/context-entries/{second['id']}", json={"text": "C"})).json()
    other = (await client.post("/api/context-entries", json={"kind": "fact", "text": "X"})).json()

    response = await client.delete(f"/api/context-entries/{third['id']}")

    assert response.status_code == 204
    active = (await client.get("/api/context-entries")).json()
    assert [item["id"] for item in active] == [other["id"]]
    replaced = (await client.get("/api/context-entries", params={"status": "replaced"})).json()
    assert replaced == []


async def test_another_customers_entry_answers_404(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    foreign = await ContextEntryRepository(session=session).create(
        owner_id=uuid4(), kind="fact", status="active", text="Not yours", source="customer"
    )
    path = f"/api/context-entries/{foreign.id}"

    patched = await client.patch(path, json={"text": "Mine now"})
    deleted = await client.delete(path)

    assert (patched.status_code, deleted.status_code) == (404, 404)
    assert await ContextEntryRepository(session=session).get_by_id(entity_id=foreign.id) is not None
    assert (await client.get("/api/context-entries")).json() == []


async def test_the_entry_over_the_limit_answers_409(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    repository = ContextEntryRepository(session=session)
    for number in range(ACTIVE_ENTRIES_MAX):
        await repository.create(
            owner_id=DEMO_USER_ID, kind="fact", status="active", text=f"{number}", source="customer"
        )

    response = await client.post("/api/context-entries", json={"kind": "fact", "text": "one more"})

    assert response.status_code == 409


async def test_text_over_300_characters_answers_422(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/context-entries", json={"kind": "fact", "text": "x" * 301})

    assert response.status_code == 422
