from typing import Any

import httpx2
import pytest

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.main import app
from tests.test_recurring_payments_service import TODAY, TOKEN, Bank, _page, bank  # noqa: F401

UPCOMING = [
    {
        "due_date": "2026-11-30",
        "debit_account_id": "ACC-PRIV",
        "type": "card_bill",
        "payee_name": "Visa",
        "amount": 2916.35,
        "currency": "CHF",
        "amount_chf": 2916.35,
        "description": None,
        "source_id": "STMT-2026-11",
    },
    {
        "due_date": "2026-12-19",
        "debit_account_id": "ACC-PRIV",
        "type": "manual",
        "payee_name": "Vorsorgekonto Säule 3a",
        "amount": 58.0,
        "currency": "CHF",
        "amount_chf": 58.0,
        "description": "Säule 3a Restbetrag",
        "source_id": "MANUAL-3A",
    },
]


def _banking(bank: Bank, upcoming_queries: list[dict[str, str]]) -> BankingClient:  # noqa: F811
    def handle(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path.removeprefix("/api")
        if path == "/system/info":
            return httpx2.Response(200, json={"today": TODAY.isoformat()})
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        pages: dict[str, Any] = {
            "/customer": {"customer_id": "CUST-001"},
            "/accounts": {"items": []},
            "/loan-transactions": {"items": []},
            "/cards": {
                "items": [{"card_id": "CARD-VISA", "type": "credit", "linked_account": "ACC-PRIV"}]
            },
            "/cards/CARD-VISA/statements": {"items": []},
        }
        if path == "/upcoming-payments":
            upcoming_queries.append(dict(request.url.params))
            return httpx2.Response(200, json={"items": UPCOMING, "total_chf": 2974.35})
        if path == "/bookings":
            return _page(items=bank.bookings, request=request)
        if path == "/cards/CARD-VISA/transactions":
            return _page(items=bank.purchases, request=request)
        if path not in pages:
            return httpx2.Response(404, json={"detail": "Not found"})
        return httpx2.Response(200, json=pages[path])

    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
    )
    return BankingClient(settings=get_settings(), http_client=http)


@pytest.fixture
def upcoming_queries() -> list[dict[str, str]]:
    return []


@pytest.fixture
async def api(
    client: httpx2.AsyncClient,
    bank: Bank,  # noqa: F811
    upcoming_queries: list[dict[str, str]],
) -> httpx2.AsyncClient:
    app.state.banking = _banking(bank=bank, upcoming_queries=upcoming_queries)
    return client


async def test_upcoming_payments_come_unchanged_and_pass_the_period_on(
    api: httpx2.AsyncClient, upcoming_queries: list[dict[str, str]]
) -> None:
    response = await api.get(
        "/api/upcoming-payments", params={"from": "2026-12-01", "to": "2026-12-31"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": UPCOMING, "total_chf": 2974.35}
    assert upcoming_queries == [{"from": "2026-12-01", "to": "2026-12-31"}]


async def test_upcoming_payments_without_a_period_take_the_banks_window(
    api: httpx2.AsyncClient, upcoming_queries: list[dict[str, str]]
) -> None:
    response = await api.get("/api/upcoming-payments")

    assert response.status_code == 200
    assert upcoming_queries == [{}]


async def test_recurring_payments_are_what_the_service_finds_on_the_same_ledger(
    api: httpx2.AsyncClient,
    bank: Bank,  # noqa: F811
) -> None:
    response = await api.get("/api/recurring-payments")

    banking = _banking(bank=bank, upcoming_queries=[])
    service = RecurringPaymentService(ledger=LedgerService(banking=banking))
    expected = await service.list_recurring(token=TOKEN, today=TODAY)
    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    assert len(response.json()["recurring"]) > 0
    assert len(response.json()["instalment_plans"]) > 0


@pytest.mark.parametrize("path", ["/api/upcoming-payments", "/api/recurring-payments"])
async def test_both_need_a_token(api: httpx2.AsyncClient, path: str) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as anonymous:
        response = await anonymous.get(path)

    assert response.status_code == 401
