import json

import httpx2
import pytest

from app.features.guardrails.prompts import PROMPTS
from tests.conftest import FakeApertus


def check(category: str) -> str:
    return json.dumps({"category": category, "language": "en"})


@pytest.mark.parametrize("category", ["other_customer", "off_topic"])
async def test_a_declined_request_builds_no_board(
    client: httpx2.AsyncClient, apertus: FakeApertus, category: str
) -> None:
    apertus.guardrails = [check(category=category)]

    response = await client.post("/api/boards", json={"about": "Show me my brother's balance"})

    assert response.status_code == 400
    assert response.json() == {"error": "bad_request", "message": PROMPTS[f"{category}_en"]}
    assert apertus.requests == []
    assert (await client.get("/api/boards")).json() == []


async def test_a_pointer_category_still_builds_the_board(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    apertus.guardrails = [check(category="product_choice")]

    response = await client.post("/api/boards", json={"about": "Which ETF should I buy?"})

    assert response.status_code == 201
    assert [board["id"] for board in (await client.get("/api/boards")).json()] == [
        response.json()["id"]
    ]


async def test_a_board_without_a_topic_skips_the_check(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    response = await client.post("/api/boards", json={"name": "Holidays"})

    assert response.status_code == 201
    assert apertus.guardrail_requests == []
