from typing import Any

import httpx2

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from evals.ledger_check import check_customer

TOKEN = "lukas-token"
ACCOUNTS = [
    {
        "account_id": "ACC-PRIV",
        "type": "current",
        "iban": "CH06 0888 8000 0044 1002 0",
        "opening_balance": 1000.0,
        "current_balance": 7739.3,
    },
]


def _booking(booking_id: str, transaction_type: str, amount: float, **fields: Any) -> dict:
    return {
        "booking_id": booking_id,
        "account_id": "ACC-PRIV",
        "booking_date": "2026-10-30",
        "amount": amount,
        "booking_text": f"Text of {booking_id}",
        "transaction_type": transaction_type,
    } | fields


BOOKINGS = [
    _booking("BK-1", "salary", 8150.0),
    _booking("BK-2", "debit_card", -212.1),
    _booking("BK-3", "card_settlement", -279.85, reference="STMT-2026-09"),
    _booking("BK-4", "loan_interest", -918.75),
]
PURCHASES = [
    {
        "card_transaction_id": f"CTX-{index}",
        "card_id": "CARD-VISA",
        "transaction_date": f"2026-{month}-12",
        "merchant_text": "GALAXUS.CH ZUERICH",
        "amount_chf": amount,
        "statement_id": f"STMT-2026-{month}",
    }
    for index, (month, amount) in enumerate([("09", 300.0), ("09", -20.15), ("10", 45.5)])
]
LOAN_CHARGES = [
    {
        "loan_tx_id": "LTX-1",
        "loan_id": "LOAN-03",
        "type": "interest",
        "amount": 918.75,
        "booking_id": "BK-4",
    }
]


def _statements(october_total: float) -> list[dict]:
    return [
        # Its purchases fall before the data, so it is skipped.
        {
            "statement_id": "STMT-2023-11",
            "card_id": "CARD-VISA",
            "status": "settled",
            "period_to": "2023-11-30",
            "total_chf": 2264.35,
            "booking_id": None,
        },
        {
            "statement_id": "STMT-2026-09",
            "card_id": "CARD-VISA",
            "status": "settled",
            "period_to": "2026-09-30",
            "total_chf": 279.85,
            "booking_id": "BK-3",
        },
        {
            "statement_id": "STMT-2026-10",
            "card_id": "CARD-VISA",
            "status": "settled",
            "period_to": "2026-10-31",
            "total_chf": october_total,
            "booking_id": None,
        },
    ]


def _page(items: list[dict], request: httpx2.Request, **sums: float) -> httpx2.Response:
    offset = int(request.url.params["offset"]) if "offset" in request.url.params else 0
    limit = int(request.url.params["limit"])
    page = {"items": items[offset : offset + limit], "total": len(items)}
    return httpx2.Response(200, json=page | sums)


def _ledger(october_total: float) -> LedgerService:
    """The ledger over a bank faked at the HTTP level whose sums come from its own items."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/system/info":
            return httpx2.Response(200, json={"today": "2026-11-27", "data_from": "2023-12-01"})
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        path = request.url.path.removeprefix("/api")
        if path == "/accounts":
            return httpx2.Response(200, json={"items": ACCOUNTS})
        if path == "/loan-transactions":
            return httpx2.Response(200, json={"items": LOAN_CHARGES})
        if path == "/cards":
            cards = [
                {"card_id": "CARD-DEBIT", "type": "debit", "linked_account": "ACC-PRIV"},
                {"card_id": "CARD-VISA", "type": "credit", "linked_account": "ACC-PRIV"},
            ]
            return httpx2.Response(200, json={"items": cards})
        if path == "/cards/CARD-VISA/statements":
            return httpx2.Response(200, json={"items": _statements(october_total=october_total)})
        if path == "/bookings":
            transaction_type = request.url.params.get("transaction_type")
            items = [
                booking
                for booking in BOOKINGS
                if transaction_type is None or booking["transaction_type"] == transaction_type
            ]
            amounts = [booking["amount"] for booking in items]
            return _page(
                items=items,
                request=request,
                sum_credit=sum(amount for amount in amounts if amount > 0),
                sum_debit=sum(amount for amount in amounts if amount < 0),
            )
        if path == "/cards/CARD-VISA/transactions":
            total = sum(purchase["amount_chf"] for purchase in PURCHASES)
            return _page(items=PURCHASES, request=request, sum_chf=total)
        return httpx2.Response(404, json={"detail": "Not found"})

    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
    )
    return LedgerService(banking=BankingClient(settings=get_settings(), http_client=http))


async def test_a_ledger_that_adds_up_passes() -> None:
    failures, skipped, _ = await check_customer(ledger=_ledger(october_total=45.5), token=TOKEN)

    assert failures == []
    assert skipped == ["STMT-2023-11"]


async def test_a_statement_off_by_five_rappen_fails_and_is_named() -> None:
    failures, _, _ = await check_customer(ledger=_ledger(october_total=45.55), token=TOKEN)

    assert failures == [
        "statement STMT-2026-10: 1 purchases add up to 45.50, the statement total is 45.55"
    ]
