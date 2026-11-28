import asyncio
import json
from typing import Any
from uuid import UUID

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import owner_id
from app.features.transaction_tags.categorisation_runs import wait_for_runs
from app.features.transaction_tags.personal_tag_service import PersonalTagService
from app.features.transaction_tags.repository import TransactionTagRepository
from app.features.transaction_tags.schemas import Categorisation, CategorisationScope, Progress
from app.features.transaction_tags.service import TransactionTagService
from app.features.transaction_tags.severity_service import SeverityService
from app.main import app
from tests.conftest import FakeApertus
from tests.test_transaction_tags import (
    LUKAS_BOOKINGS,
    _bank_client,
    _categorise_only,
    _rows_of,
    _tags,
)

LUKAS = owner_id(customer_id="CUST-001")
ANSWERS = {
    "Einkauf": ("groceries", "high", "shopping"),
    "Gartenmoebel": ("shopping", "low", "shopping"),
    "Miete": ("housing", "medium", "pets"),
    "Sushi": ("restaurants", "low", "leisure_travel"),
}


def _answer(request_body: dict[str, Any]) -> str:
    """A fake Apertus: an alternative per keyword, one equal to its category, one unknown."""
    answers = []
    for ref, row in _rows_of(request_body=request_body).items():
        keyword = next(word for word in ANSWERS if word in json.dumps(row))
        category, certainty, alternative = ANSWERS[keyword]
        answers.append(
            {"ref": ref, "category": category, "certainty": certainty, "alternative": alternative}
        )
    return json.dumps({"rows": answers})


@pytest.fixture
async def lukas(client: httpx2.AsyncClient, apertus: FakeApertus) -> httpx2.AsyncClient:
    app.state.banking = _bank_client(
        bookings_by_token={"customer-token": ("CUST-001", LUKAS_BOOKINGS)}
    )
    apertus.structured_reply = _answer
    return client


def _system(request_body: dict[str, Any]) -> str:
    return request_body["messages"][0]["content"]


def _decisions(request_body: dict[str, Any]) -> list[dict[str, str]]:
    block = _system(request_body=request_body).split("<decisions>\n")[1].split("\n</decisions>")[0]
    return [json.loads(line) for line in block.splitlines()]


async def _rejudge(api: httpx2.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def skip(*args: object, **kwargs: object) -> None:
        return None

    with monkeypatch.context() as patch:
        patch.setattr(SeverityService, "create_proposal", skip)
        patch.setattr(PersonalTagService, "create_inference", skip)
        response = await api.post("/api/categorisations", json={"scope": "unconfirmed"})
        assert response.status_code == 202
        await wait_for_runs()


async def test_the_second_choice_is_stored_unless_it_is_the_same_or_unknown(
    lukas: httpx2.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    tags = await _tags(api=lukas)
    assert tags["BK-1"]["category_alternative"] == "shopping"
    assert tags["BK-2"]["category_alternative"] is None
    assert tags["BK-3"]["category_alternative"] is None
    assert tags["CTX-1"]["category_alternative"] == "leisure_travel"


async def test_a_customer_category_is_listed_offered_to_apertus_and_used(
    lukas: httpx2.AsyncClient, apertus: FakeApertus, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = await lukas.post(
        "/api/categories", json={"name": " pets ", "description": "Food and vet for our cat"}
    )

    assert created.status_code == 201
    assert created.json() == {
        "name": "pets",
        "description": "Food and vet for our cat",
        "custom": True,
    }
    listed = (await lukas.get("/api/categories")).json()
    assert listed[0] == {"name": "housing", "description": "", "custom": False}
    assert listed[-1]["name"] == "pets"

    await _categorise_only(api=lukas, monkeypatch=monkeypatch)

    (request,) = apertus.requests
    assert '{"name": "pets", "description": "Food and vet for our cat"}' in _system(
        request_body=request
    )
    instruction = request["messages"][-1]["content"]
    schema = json.loads(instruction.split("JSON schema:\n")[1])["$defs"]["RowCategory"]
    assert "pets" in schema["properties"]["category"]["enum"]
    assert (await _tags(api=lukas))["BK-3"]["category_alternative"] == "pets"
    corrected = await lukas.post(
        "/api/category-corrections",
        json={"scope": "payee", "key": "Immo AG", "category": "pets"},
    )
    assert corrected.status_code == 201


async def test_a_category_name_that_exists_is_refused(lukas: httpx2.AsyncClient) -> None:
    await lukas.post("/api/categories", json={"name": "Pets"})

    for name in ("pets", "Groceries", "not_categorised"):
        response = await lukas.post("/api/categories", json={"name": name})
        assert response.status_code == 409, name
    assert (await lukas.post("/api/categories", json={"name": " "})).status_code == 422


async def test_judging_again_replaces_model_answers_and_keeps_the_customers(
    lukas: httpx2.AsyncClient, apertus: FakeApertus, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)
    await lukas.post(
        "/api/category-corrections",
        json={"scope": "booking", "key": "booking:BK-3", "category": "other"},
    )
    apertus.requests.clear()

    def all_shopping(request_body: dict[str, Any]) -> str:
        refs = _rows_of(request_body=request_body)
        return json.dumps(
            {"rows": [{"ref": ref, "category": "shopping", "certainty": "high"} for ref in refs]}
        )

    apertus.structured_reply = all_shopping
    await _rejudge(api=lukas, monkeypatch=monkeypatch)

    tags = await _tags(api=lukas)
    assert tags["BK-1"]["category"] == "shopping"
    assert tags["CTX-1"]["category"] == "shopping"
    assert tags["BK-3"]["category"] == "other"
    assert tags["BK-4"]["category"] == "loan_leasing"
    sent = {row["text"] for request in apertus.requests for row in _rows_of(request).values()}
    assert not any("Miete" in text or "Hypothek" in text for text in sent)


async def test_every_decision_reaches_the_prompt_with_a_booking_text(
    lukas: httpx2.AsyncClient, apertus: FakeApertus, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)
    await lukas.post(
        "/api/category-corrections",
        json={"scope": "payee", "key": "Migros", "category": "groceries"},
    )
    await lukas.post(
        "/api/category-corrections",
        json={"scope": "booking", "key": "card_transaction:CTX-1", "category": "leisure_travel"},
    )
    apertus.requests.clear()

    await _rejudge(api=lukas, monkeypatch=monkeypatch)

    (request,) = apertus.requests
    assert _decisions(request_body=request) == [
        {"payee": "sushi tokyo", "text": "SUSHI TOKYO", "category": "leisure_travel"},
        {"payee": "migros", "text": "Einkauf", "category": "groceries"},
    ]


async def test_asking_to_judge_again_during_a_run_judges_again_after_it(
    lukas: httpx2.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = asyncio.Event()
    scopes: list[str] = []
    original = TransactionTagService.create_categorisation

    async def held(
        self: TransactionTagService,
        owner_id: UUID,
        token: str,
        scope: CategorisationScope,
        progress: Progress | None = None,
    ) -> Categorisation:
        scopes.append(scope)
        await release.wait()
        return await original(self, owner_id=owner_id, token=token, scope=scope, progress=progress)

    async def skip(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(TransactionTagService, "create_categorisation", held)
    monkeypatch.setattr(SeverityService, "create_proposal", skip)
    monkeypatch.setattr(PersonalTagService, "create_inference", skip)

    first = await lukas.post("/api/categorisations")
    again = await lukas.post("/api/categorisations", json={"scope": "unconfirmed"})
    release.set()
    await wait_for_runs()

    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert scopes == ["untagged", "unconfirmed"]
    runs = (await lukas.get("/api/categorisations")).json()
    assert [run["status"] for run in runs] == ["done", "done"]
    assert runs[1]["id"] == first.json()["id"]


async def test_judging_again_never_overwrites_a_decision_made_during_the_run(
    lukas: httpx2.AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _categorise_only(api=lukas, monkeypatch=monkeypatch)
    await lukas.post(
        "/api/category-corrections",
        json={"scope": "payee", "key": "Migros", "category": "shopping"},
    )
    model_row = {
        "owner_id": LUKAS,
        "category": "health",
        "category_set_by": "model",
        "category_model": "fake-smart",
        "category_confirmed": False,
        "category_certainty": "low",
        "category_alternative": None,
    }

    # The run started before the decision and writes its answers after it.
    changed = await TransactionTagRepository(session=session).replace_model_categories(
        values=[
            {**model_row, "row_source": "booking", "row_id": "BK-1"},
            {**model_row, "row_source": "booking", "row_id": "BK-3"},
        ]
    )

    tags = await _tags(api=lukas)
    assert changed == 1
    assert tags["BK-1"]["category"] == "shopping"
    assert tags["BK-1"]["category_set_by"] == "customer"
    assert tags["BK-3"]["category"] == "health"
