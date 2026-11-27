from typing import Any

import httpx2

from app.features.context_entries.tools import ONE_PROPOSAL_PER_TURN, PROPOSE
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import FakeApertus

JAPAN = "I want to save CHF 6'000 for Japan by 30 June 2027"
GOAL = {
    "kind": "goal",
    "text": "Japan trip in 2027",
    "amount_chf": 6000,
    "target_date": "2027-06-30",
}


LIST = ToolRequest(reason="Needs my notes.", tool="list_context_entries", arguments={})


def _propose(**arguments: Any) -> ToolRequest:
    return ToolRequest(reason="Remember it.", tool=PROPOSE, arguments=arguments)


async def _turn(
    client: httpx2.AsyncClient, apertus: FakeApertus, requests: list[ToolRequest]
) -> list[dict[str, Any]]:
    """One turn whose decision makes these calls; returns its calls."""
    apertus.decisions = [ToolDecision(plan="Remember.", calls=requests).model_dump_json()]
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}"
    response = await client.post(f"{url}/messages", json={"content": JAPAN})
    assert response.status_code == 201
    return (await client.get(f"{url}/tool-calls")).json()


async def _listed(client: httpx2.AsyncClient, apertus: FakeApertus) -> list[str]:
    """The entries list_context_entries gives the model in a new turn, as kind, text and amount."""
    (call,) = await _turn(client=client, apertus=apertus, requests=[LIST])
    return [
        f"{entry['kind']}: {entry['text']}; {entry['amount_chf']}"
        for entry in call["result"]["entries"]
    ]


async def _entries(client: httpx2.AsyncClient, status: str) -> list[dict[str, Any]]:
    return (await client.get("/api/context-entries", params={"status": status})).json()


async def test_the_japan_sentence_stores_one_proposed_goal(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    (call,) = await _turn(client=client, apertus=apertus, requests=[_propose(**GOAL)])

    assert call["error"] is None
    (proposal,) = await _entries(client=client, status="proposed")
    assert (proposal["kind"], proposal["amount_chf"], proposal["target_date"]) == (
        "goal",
        6000,
        "2027-06-30",
    )
    assert (proposal["source"], proposal["source_id"]) == ("chat", call["id"])
    assert call["result"]["id"] == proposal["id"]
    assert await _entries(client=client, status="active") == []

    assert await _listed(client=client, apertus=apertus) == []


async def test_confirming_with_a_changed_amount_stores_that_amount_as_active(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await _turn(client=client, apertus=apertus, requests=[_propose(**GOAL)])
    (proposal,) = await _entries(client=client, status="proposed")

    response = await client.patch(
        f"/api/context-entries/{proposal['id']}", json={"status": "active", "amount_chf": 7500}
    )

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["amount_chf"]) == ("active", 7500)
    (active,) = await _entries(client=client, status="active")
    assert (active["id"], active["amount_chf"]) == (proposal["id"], 7500)
    assert await _listed(client=client, apertus=apertus) == ["goal: Japan trip in 2027; 7500.00"]


async def test_confirming_a_replacement_leaves_one_active_and_one_replaced(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    old = (await client.post("/api/context-entries", json=GOAL)).json()
    new_goal = {**GOAL, "text": "Japan trip in 2028", "target_date": "2028-06-30"}
    await _turn(
        client=client, apertus=apertus, requests=[_propose(**new_goal, replaces="japan trip")]
    )
    (proposal,) = await _entries(client=client, status="proposed")
    assert proposal["replaces_id"] == old["id"]

    response = await client.patch(
        f"/api/context-entries/{proposal['id']}", json={"status": "active"}
    )

    assert response.status_code == 200
    assert [entry["id"] for entry in await _entries(client=client, status="active")] == [
        proposal["id"]
    ]
    (replaced,) = await _entries(client=client, status="replaced")
    assert (replaced["id"], replaced["replaced_by_id"]) == (old["id"], proposal["id"])


async def test_a_replacement_may_change_only_the_amount(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    old = (await client.post("/api/context-entries", json=GOAL)).json()

    (call,) = await _turn(
        client=client,
        apertus=apertus,
        requests=[_propose(**{**GOAL, "amount_chf": 8000}, replaces="Japan trip")],
    )

    assert call["error"] is None
    (proposal,) = await _entries(client=client, status="proposed")
    assert (proposal["amount_chf"], proposal["replaces_id"]) == (8000, old["id"])


async def test_a_replacement_without_a_match_lists_the_active_entries(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await client.post("/api/context-entries", json=GOAL)

    (call,) = await _turn(
        client=client, apertus=apertus, requests=[_propose(kind="fact", text="X", replaces="car")]
    )

    assert "- goal: Japan trip in 2027" in call["error"]
    assert await _entries(client=client, status="proposed") == []


async def test_a_dismissed_proposal_stays_out_and_is_not_stored_again(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await _turn(client=client, apertus=apertus, requests=[_propose(**GOAL)])
    (proposal,) = await _entries(client=client, status="proposed")
    response = await client.patch(
        f"/api/context-entries/{proposal['id']}", json={"status": "dismissed"}
    )
    assert response.json()["status"] == "dismissed"

    (call,) = await _turn(client=client, apertus=apertus, requests=[_propose(**GOAL)])

    assert await _listed(client=client, apertus=apertus) == []
    assert "dismissed" in call["error"]
    assert await _entries(client=client, status="proposed") == []
    assert len(await _entries(client=client, status="dismissed")) == 1


async def test_a_second_proposal_in_one_turn_is_refused(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    (first, second) = await _turn(
        client=client,
        apertus=apertus,
        requests=[_propose(**GOAL), _propose(kind="fact", text="I live in Zurich")],
    )

    assert first["error"] is None
    assert second["error"] == ONE_PROPOSAL_PER_TURN
    assert len(await _entries(client=client, status="proposed")) == 1


async def test_a_proposal_needs_a_status_and_an_active_entry_takes_none(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    await _turn(client=client, apertus=apertus, requests=[_propose(**GOAL)])
    (proposal,) = await _entries(client=client, status="proposed")
    active = (await client.post("/api/context-entries", json={**GOAL, "text": "Car"})).json()

    without_status = await client.patch(
        f"/api/context-entries/{proposal['id']}", json={"amount_chf": 1}
    )
    dismissing_active = await client.patch(
        f"/api/context-entries/{active['id']}", json={"status": "dismissed"}
    )

    assert (without_status.status_code, dismissing_active.status_code) == (400, 400)
