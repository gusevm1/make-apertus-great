from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.features.ledger import service as ledger_service
from app.features.ledger.service import LedgerService

TOKEN = "lukas-token"
ACCOUNTS = [
    {"account_id": "ACC-PRIV", "type": "current", "iban": "CH06 0888 8000 0044 1002 0"},
    {"account_id": "ACC-TAX", "type": "savings", "iban": "CH14 0888 8000 0044 1113 7"},
]


def _booking(booking_id: str, transaction_type: str, amount: float, **fields: Any) -> dict:
    return {
        "booking_id": booking_id,
        "account_id": "ACC-PRIV",
        "booking_date": "2026-10-30",
        "amount": amount,
        "booking_text": f"Text of {booking_id}",
        "counterparty_name": None,
        "counterparty_iban": None,
        "transaction_type": transaction_type,
        "reference": None,
        "card_id": None,
        "original_amount": None,
        "original_currency": None,
    } | fields


BOOKINGS = [
    _booking("BK-1", "salary", 8150.0),
    _booking("BK-2", "debit_card", -212.1, card_id="CARD-DEBIT"),
    # The bank writes this IBAN without spaces; it is still the customer's own account.
    _booking("BK-3", "standing_order", -500.0, counterparty_iban="CH1408888000004411137"),
    _booking("BK-4", "standing_order", -2140.0, counterparty_iban="CH93 0076 2011 6238 5295 7"),
    _booking("BK-5", "card_settlement", -70.0, reference="STMT-2026-10"),
    _booking("BK-6", "securities_buy", -1000.0),
    _booking("BK-7", "account_transfer", 300.0, counterparty_iban="CH14 0888 8000 0044 1113 7"),
    _booking("BK-8", "loan_interest", -918.75),
]
PURCHASES = [
    {
        "card_transaction_id": "CTX-1",
        "card_id": "CARD-VISA",
        "transaction_date": "2026-10-12",
        "merchant_text": "DROPBOX*QX81 DUBLIN",
        "merchant_name": "Dropbox",
        "original_amount": 11.99,
        "original_currency": "USD",
        "amount_chf": 10.96,
        "statement_id": "STMT-2026-10",
    },
    {
        "card_transaction_id": "CTX-2",
        "card_id": "CARD-VISA",
        "transaction_date": "2026-10-20",
        "merchant_text": "ZALANDO RETOURE",
        "merchant_name": "Zalando",
        "original_amount": None,
        "original_currency": None,
        "amount_chf": -40.0,
        "statement_id": "STMT-2026-10",
    },
]
LOAN_CHARGES = [{"booking_id": "BK-8", "loan_id": "LOAN-03", "type": "interest"}]


def _page(items: list[dict], request: httpx2.Request) -> httpx2.Response:
    offset = int(request.url.params["offset"])
    limit = int(request.url.params["limit"])
    return httpx2.Response(200, json={"items": items[offset : offset + limit], "total": len(items)})


@pytest.fixture
def pages_read() -> list[str]:
    return []


@pytest.fixture
def ledger(pages_read: list[str]) -> LedgerService:
    """The ledger over a bank faked at the HTTP level; an unknown path is a 404 and fails."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        path = request.url.path.removeprefix("/api")
        if path == "/accounts":
            return httpx2.Response(200, json={"items": ACCOUNTS})
        if path == "/loan-transactions":
            return httpx2.Response(200, json={"items": LOAN_CHARGES, "sum_chf": 918.75})
        if path == "/cards":
            cards = [
                {"card_id": "CARD-DEBIT", "type": "debit", "linked_account": "ACC-PRIV"},
                {"card_id": "CARD-VISA", "type": "credit", "linked_account": "ACC-PRIV"},
            ]
            return httpx2.Response(200, json={"items": cards})
        if path == "/bookings":
            pages_read.append(f"bookings offset={request.url.params['offset']}")
            return _page(items=BOOKINGS, request=request)
        if path == "/cards/CARD-VISA/transactions":
            pages_read.append(f"card offset={request.url.params['offset']}")
            return _page(items=PURCHASES, request=request)
        return httpx2.Response(404, json={"detail": "Not found"})

    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
    )
    return LedgerService(banking=BankingClient(settings=get_settings(), http_client=http))


async def test_each_movement_gets_its_kind(ledger: LedgerService) -> None:
    rows = await ledger.list_rows(token=TOKEN)

    assert {row.id: row.kind for row in rows} == {
        "BK-1": "credit",
        "BK-2": "spending",
        "BK-3": "own_transfer",
        "BK-4": "spending",
        "BK-5": "card_settlement",
        "BK-6": "own_transfer",
        "BK-7": "own_transfer",
        "BK-8": "spending",
        "CTX-1": "spending",
        "CTX-2": "credit",
    }


async def test_card_purchases_replace_the_bill_with_the_sign_of_a_booking(
    ledger: LedgerService,
) -> None:
    rows = {row.id: row for row in await ledger.list_rows(token=TOKEN)}

    purchase, refund, bill = rows["CTX-1"], rows["CTX-2"], rows["BK-5"]
    assert (purchase.amount_chf, purchase.original_amount) == (Decimal("-10.96"), Decimal("-11.99"))
    assert refund.amount_chf == Decimal("40.0")
    assert (purchase.account_id, purchase.card_id) == ("ACC-PRIV", "CARD-VISA")
    assert purchase.statement_id == bill.statement_id == "STMT-2026-10"
    assert str(purchase.date) == "2026-10-12"


async def test_a_loan_booking_carries_its_tranche_and_adds_no_row(ledger: LedgerService) -> None:
    rows = await ledger.list_rows(token=TOKEN)

    (interest,) = [row for row in rows if row.loan_id is not None]
    assert (interest.id, interest.loan_id, interest.loan_charge) == ("BK-8", "LOAN-03", "interest")
    assert len(rows) == len(BOOKINGS) + len(PURCHASES)


async def test_every_page_is_read_once(
    ledger: LedgerService, pages_read: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ledger_service, "PAGE_SIZE", 3)

    rows = await ledger.list_rows(token=TOKEN)

    assert sorted(row.id for row in rows) == sorted(
        [b["booking_id"] for b in BOOKINGS] + [p["card_transaction_id"] for p in PURCHASES]
    )
    assert pages_read == [
        "bookings offset=0",
        "bookings offset=3",
        "bookings offset=6",
        "card offset=0",
    ]


async def test_a_read_off_the_list_never_reaches_the_bank(
    ledger: LedgerService, pages_read: list[str]
) -> None:
    for path in ["/admin/reset", "/auth/login", "/accounts/../bookings", "/cards/./transactions"]:
        with pytest.raises(BadRequestError, match="is not a read the bank data allows"):
            await ledger.read(path=path, token=TOKEN)

    assert pages_read == []


async def test_a_read_on_the_list_answers_as_the_bank_does(ledger: LedgerService) -> None:
    assert await ledger.read(path="/accounts", token=TOKEN) == {"items": ACCOUNTS}
