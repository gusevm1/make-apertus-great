from datetime import date
from decimal import Decimal
from typing import Any

import httpx2
import pytest

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.features.bank_data.service import BankDataService
from app.features.bank_data.tools import get_tools
from app.features.ledger import service as ledger_service
from app.features.ledger.schemas import Filters, SearchMovementsArgs, SumByCounterpartyArgs
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
    for path in [
        "/admin/reset",
        "/auth/login",
        "/accounts/../bookings",
        "/cards/./transactions",
        "/accounts\n",
    ]:
        with pytest.raises(BadRequestError, match="is not a read the bank data allows"):
            await ledger.read(path=path, token=TOKEN)

    assert pages_read == []


async def test_a_read_on_the_list_answers_as_the_bank_does(ledger: LedgerService) -> None:
    assert await ledger.read(path="/accounts", token=TOKEN) == {"items": ACCOUNTS}


async def test_an_id_of_dots_cannot_climb_to_another_path(
    ledger: LedgerService, pages_read: list[str]
) -> None:
    tools = {
        tool.name: tool for tool in get_tools(service=BankDataService(ledger=ledger), token=TOKEN)
    }
    preview = tools["get_balance_preview"]

    with pytest.raises(BadRequestError, match="is not a read the bank data allows"):
        await preview.handler(preview.args_schema(account_id=".."))

    assert pages_read == []


async def test_a_card_purchase_and_the_bill_that_pays_it_count_once(ledger: LedgerService) -> None:
    found = await ledger.search_movements(token=TOKEN, args=SearchMovementsArgs())
    bills = await ledger.search_movements(
        token=TOKEN, args=SearchMovementsArgs(kind=["card_settlement"])
    )

    assert sorted(found.row_ids) == ["BK-1", "BK-2", "BK-4", "BK-8", "CTX-1", "CTX-2"]
    assert (found.money_out_chf, found.money_in_chf) == (Decimal("-3281.81"), Decimal("8190.0"))
    assert bills.row_ids == ["BK-5"]


async def test_text_matches_any_word_and_amounts_have_no_sign(ledger: LedgerService) -> None:
    shops = await ledger.search_movements(
        token=TOKEN, args=SearchMovementsArgs(text=["DROPBOX", "zalando"])
    )
    large = await ledger.search_movements(
        token=TOKEN, args=SearchMovementsArgs(amount_min=Decimal(900), sort="largest")
    )

    assert sorted(shops.row_ids) == ["CTX-1", "CTX-2"]
    assert [row.id for row in large.rows] == ["BK-1", "BK-4", "BK-8"]


async def test_only_the_limit_is_listed_but_the_sums_cover_all(ledger: LedgerService) -> None:
    found = await ledger.search_movements(token=TOKEN, args=SearchMovementsArgs(limit=2))

    assert (len(found.rows), found.rows_not_listed, found.count) == (2, 4, 6)
    assert found.money_out_chf == Decimal("-3281.81")


async def test_every_month_of_the_period_is_listed_also_without_a_match(
    ledger: LedgerService,
) -> None:
    filters = Filters(date_from=date(2026, 8, 1), date_to=date(2026, 10, 31), kind=["spending"])

    sums = await ledger.sum_by_month(token=TOKEN, filters=filters)

    assert [(month.month, month.count) for month in sums.months] == [
        ("2026-08", 0),
        ("2026-09", 0),
        ("2026-10", 4),
    ]
    assert sums.months[2].money_out_chf == Decimal("-3281.81")
    assert sorted(sums.row_ids["2026-10"]) == ["BK-2", "BK-4", "BK-8", "CTX-1"]


async def test_the_largest_counterparties_come_first_and_the_rest_is_one_group(
    ledger: LedgerService,
) -> None:
    args = SumByCounterpartyArgs(kind=["spending"], limit=2)

    sums = await ledger.sum_by_counterparty(token=TOKEN, args=args)

    assert [group.money_out_chf for group in sums.counterparties] == [
        Decimal("-2140.0"),
        Decimal("-918.75"),
    ]
    assert sums.others is not None
    assert (sums.others.count, sums.others.money_out_chf) == (2, Decimal("-223.06"))
    assert sorted(sums.row_ids["others"]) == ["BK-2", "CTX-1"]


async def test_three_tools_in_one_turn_read_the_bank_once(
    ledger: LedgerService,
    pages_read: list[str],
) -> None:
    await ledger.search_movements(token=TOKEN, args=SearchMovementsArgs())
    await ledger.sum_by_month(token=TOKEN, filters=Filters())
    await ledger.sum_by_counterparty(token=TOKEN, args=SumByCounterpartyArgs())

    assert pages_read == ["bookings offset=0", "card offset=0"]


async def test_a_word_no_movement_contains_asks_for_names(ledger: LedgerService) -> None:
    with pytest.raises(BadRequestError, match="sum_by_counterparty"):
        await ledger.search_movements(
            token=TOKEN, args=SearchMovementsArgs.model_validate({"text": "online shops"})
        )


async def test_a_word_from_another_period_is_a_real_zero(ledger: LedgerService) -> None:
    args = SearchMovementsArgs(text=["Dropbox"], date_from=date(2026, 11, 1))

    found = await ledger.search_movements(token=TOKEN, args=args)

    assert (found.count, found.money_out_chf) == (0, Decimal(0))


async def test_words_match_at_a_word_start_and_a_bar_separates_them(ledger: LedgerService) -> None:
    found = await ledger.search_movements(
        token=TOKEN, args=SearchMovementsArgs.model_validate({"text": "zal|drop"})
    )

    assert sorted(found.row_ids) == ["CTX-1", "CTX-2"]
    with pytest.raises(BadRequestError):
        await ledger.search_movements(token=TOKEN, args=SearchMovementsArgs(text=["ando"]))


async def test_an_empty_word_is_an_error_not_a_filter_that_matches_everything() -> None:
    assert SearchMovementsArgs.model_validate({"text": "Migros|"}).text == ["Migros"]
    with pytest.raises(ValueError, match="at least 1 item"):
        SearchMovementsArgs.model_validate({"text": "|"})


async def test_without_a_period_the_months_run_from_the_first_to_the_last_row(
    ledger: LedgerService,
) -> None:
    sums = await ledger.sum_by_month(token=TOKEN, filters=Filters())

    assert [month.month for month in sums.months] == ["2026-10"]
    assert sums.months[0].count == 6
