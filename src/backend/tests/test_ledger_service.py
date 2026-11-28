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
from app.features.ledger.schemas import (
    BalanceChangeArgs,
    ComparePeriodsArgs,
    Filters,
    ForecastMonthsArgs,
    SearchMovementsArgs,
    SumByCounterpartyArgs,
    SumByGroupArgs,
    TaxYearArgs,
)
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
PERFORMANCE = {
    "points": [
        {"date": "2025-11-30", "value_chf": 64172.04},
        {"date": "2025-12-31", "value_chf": 64165.28},
    ]
}
LOAN_CHARGES = [{"booking_id": "BK-8", "loan_id": "LOAN-03", "type": "interest"}]


def _page(items: list[dict], request: httpx2.Request) -> httpx2.Response:
    offset = int(request.url.params["offset"])
    limit = int(request.url.params["limit"])
    return httpx2.Response(200, json={"items": items[offset : offset + limit], "total": len(items)})


@pytest.fixture
def pages_read() -> list[str]:
    return []


@pytest.fixture
def statements() -> list[dict]:
    return [
        {
            "statement_id": "STMT-2026-10",
            "card_id": "CARD-VISA",
            "status": "settled",
            "transactions_count": 2,
        }
    ]


@pytest.fixture
def ledger(pages_read: list[str], statements: list[dict]) -> LedgerService:
    return _fake_ledger(
        bookings=BOOKINGS, purchases=PURCHASES, statements=statements, pages_read=pages_read
    )


def _fake_ledger(
    bookings: list[dict], purchases: list[dict], statements: list[dict], pages_read: list[str]
) -> LedgerService:
    """The ledger over a bank faked at the HTTP level; an unknown path is a 404 and fails."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        path = request.url.path.removeprefix("/api")
        if path == "/accounts":
            return httpx2.Response(200, json={"items": ACCOUNTS})
        if path == "/loan-transactions":
            return httpx2.Response(200, json={"items": LOAN_CHARGES, "sum_chf": 918.75})
        if path == "/portfolio/performance" and request.url.params.get("period") == "3y":
            return httpx2.Response(200, json=PERFORMANCE)
        if path == "/cards":
            cards = [
                {"card_id": "CARD-DEBIT", "type": "debit", "linked_account": "ACC-PRIV"},
                {"card_id": "CARD-VISA", "type": "credit", "linked_account": "ACC-PRIV"},
            ]
            return httpx2.Response(200, json={"items": cards})
        if path == "/bookings":
            pages_read.append(f"bookings offset={request.url.params['offset']}")
            return _page(items=bookings, request=request)
        if path == "/cards/CARD-VISA/statements":
            return httpx2.Response(200, json={"items": statements})
        if path == "/cards/CARD-VISA/transactions":
            pages_read.append(f"card offset={request.url.params['offset']}")
            return _page(items=purchases, request=request)
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
    assert preview.handler is not None

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


async def test_months_before_the_first_or_after_the_last_row_are_not_listed(
    ledger: LedgerService,
) -> None:
    filters = Filters(date_from=date(2026, 8, 1), date_to=date(2026, 12, 31), kind=["spending"])

    sums = await ledger.sum_by_month(token=TOKEN, filters=filters, today=TODAY)

    assert [(month.month, month.count) for month in sums.months] == [("2026-10", 4)]
    assert sums.average_out_chf == sums.money_out_chf
    assert sums.months[0].money_out_chf == Decimal("-3281.81")
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
    await ledger.sum_by_month(token=TOKEN, filters=Filters(), today=TODAY)
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
    sums = await ledger.sum_by_month(token=TOKEN, filters=Filters(), today=TODAY)

    assert [month.month for month in sums.months] == ["2026-10"]
    assert sums.months[0].count == 6


async def test_purchases_on_an_open_statement_are_provisional_and_the_sums_say_how_much(
    ledger: LedgerService, statements: list[dict]
) -> None:
    statements[0]["status"] = "open"
    october = Filters(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))

    search = await ledger.search_movements(token=TOKEN, args=SearchMovementsArgs(limit=20))
    months = await ledger.sum_by_month(token=TOKEN, filters=october, today=TODAY)

    provisional = {row.id for row in search.rows if row.provisional}
    assert provisional == {"CTX-1", "CTX-2"}
    assert (search.provisional_out_chf, search.provisional_in_chf) == (
        Decimal("-10.96"),
        Decimal("40.0"),
    )
    assert months.months[0].provisional_out_chf == Decimal("-10.96")


async def test_purchases_on_a_settled_statement_are_final(ledger: LedgerService) -> None:
    search = await ledger.search_movements(token=TOKEN, args=SearchMovementsArgs(limit=20))

    assert not any(row.provisional for row in search.rows)
    assert (search.provisional_out_chf, search.provisional_in_chf) == (Decimal(0), Decimal(0))


TODAY = date(2026, 11, 27)


def _spending(booking_id: str, day: str, amount: float) -> dict:
    return _booking(booking_id, "debit_card", amount, booking_date=day)


async def test_the_trend_is_a_straight_line_through_the_full_months() -> None:
    bookings = [
        _spending("BK-AUG", "2026-08-10", -100.0),
        _spending("BK-SEP", "2026-09-10", -200.0),
        _spending("BK-OCT", "2026-10-10", -300.0),
        # November isn't over, so it stays out of the line.
        _spending("BK-NOV", "2026-11-02", -5000.0),
    ]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])

    trend = await ledger.forecast_months(
        token=TOKEN, args=ForecastMonthsArgs(months_back=3, months_ahead=2), today=TODAY
    )

    assert (trend.first_month, trend.last_month, trend.months_used) == ("2026-08", "2026-10", 3)
    assert (trend.average_chf, trend.trend_chf_per_month) == (
        Decimal("-200.00"),
        Decimal("-100.00"),
    )
    assert trend.trend_percent_per_month == Decimal("-50.00")
    assert [(month.month, month.trend_chf) for month in trend.projection] == [
        ("2026-11", Decimal("-400.00")),
        ("2026-12", Decimal("-500.00")),
    ]
    assert "BK-NOV" not in [row_id for ids in trend.row_ids.values() for row_id in ids]


async def test_a_month_without_a_match_counts_as_0_in_the_trend() -> None:
    bookings = [
        _spending("BK-AUG", "2026-08-10", -300.0),
        _spending("BK-OCT", "2026-10-10", -300.0),
    ]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])

    trend = await ledger.forecast_months(
        token=TOKEN, args=ForecastMonthsArgs(months_back=3), today=TODAY
    )

    assert [month.count for month in trend.months] == [1, 0, 1]
    assert (trend.average_chf, trend.trend_chf_per_month) == (Decimal("-200.00"), Decimal("0.00"))


async def test_a_trend_needs_three_months_the_ledger_covers() -> None:
    bookings = [
        _spending("BK-SEP", "2026-09-10", -200.0),
        _spending("BK-OCT", "2026-10-10", -300.0),
    ]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])

    with pytest.raises(BadRequestError, match="Only 2 full months"):
        await ledger.forecast_months(token=TOKEN, args=ForecastMonthsArgs(), today=TODAY)


async def test_sums_per_year_add_up_to_the_monthly_sums_of_the_period() -> None:
    bookings = [
        _spending("BK-1", "2025-11-03", -40.0),
        _spending("BK-2", "2025-12-20", -60.5),
        _spending("BK-3", "2026-01-05", -10.25),
        _booking("BK-4", "salary", 5000.0, booking_date="2026-01-25"),
    ]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])
    first, last = date(2025, 12, 1), date(2026, 1, 31)

    years = await ledger.sum_by_group(
        token=TOKEN, args=SumByGroupArgs(group_by="year", date_from=first, date_to=last)
    )
    months = await ledger.sum_by_month(
        token=TOKEN, filters=Filters(date_from=first, date_to=last), today=TODAY
    )

    assert [group.group for group in years.groups] == ["2025", "2026"]
    assert (years.money_out_chf, years.money_in_chf) == (months.money_out_chf, months.money_in_chf)
    assert sorted(sum(years.row_ids.values(), [])) == sorted(sum(months.row_ids.values(), []))


async def test_every_weekday_is_listed_and_kinds_count_only_when_asked(
    ledger: LedgerService,
) -> None:
    weekdays = await ledger.sum_by_group(token=TOKEN, args=SumByGroupArgs(group_by="weekday"))
    kinds = await ledger.sum_by_group(
        token=TOKEN, args=SumByGroupArgs(group_by="kind", kind=["spending", "own_transfer"])
    )

    assert len(weekdays.groups) == 7
    # The bookings fall on Friday 2026-10-30, the card purchases on a Monday and a Tuesday.
    assert {group.group for group in weekdays.groups if group.count > 0} == {
        "friday",
        "monday",
        "tuesday",
    }
    assert [group.group for group in kinds.groups] == ["own_transfer", "spending"]


async def test_a_history_that_starts_this_month_is_not_enough_for_a_trend() -> None:
    bookings = [_spending("BK-NOV", "2026-11-02", -50.0)]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])

    with pytest.raises(BadRequestError, match="Only 0 full months"):
        await ledger.forecast_months(token=TOKEN, args=ForecastMonthsArgs(), today=TODAY)


async def test_each_group_says_how_much_of_it_is_provisional(
    ledger: LedgerService, statements: list[dict]
) -> None:
    statements[0]["status"] = "open"

    weekdays = await ledger.sum_by_group(token=TOKEN, args=SumByGroupArgs(group_by="weekday"))

    by_day = {group.group: group for group in weekdays.groups}
    assert by_day["monday"].provisional_out_chf == Decimal("-10.96")
    assert by_day["tuesday"].provisional_in_chf == Decimal("40.0")
    assert by_day["friday"].provisional_out_chf == Decimal(0)
    assert weekdays.provisional_out_chf == Decimal("-10.96")


OCTOBER = Filters(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))


def _payment(booking_id: str, day: str, amount: float, counterparty: str = "Digitec") -> dict:
    return _booking(
        booking_id, "debit_card", amount, booking_date=day, counterparty_name=counterparty
    )


def _history(median: float, count: int = 5, counterparty: str = "Digitec") -> list[dict]:
    return [
        _payment(f"BK-{counterparty}-{index}", f"2026-0{index % 9 + 1}-05", -median, counterparty)
        for index in range(count)
    ]


async def _flags(bookings: list[dict], filters: Filters = OCTOBER) -> dict[str, str]:
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])
    found = await ledger.find_unusual_movements(token=TOKEN, filters=filters, today=TODAY)
    return {flag.movement.id: flag.reason for flag in found.movements}


async def test_a_payment_far_above_the_counterpartys_median_is_flagged_with_it() -> None:
    ledger = _fake_ledger(
        bookings=[*_history(median=50.0), _payment("BK-BIG", "2026-10-10", -151.0)],
        purchases=[],
        statements=[],
        pages_read=[],
    )

    found = await ledger.find_unusual_movements(token=TOKEN, filters=OCTOBER, today=TODAY)

    [flag] = found.movements
    assert (flag.reason, flag.movement.id) == ("unusual_amount", "BK-BIG")
    assert (flag.typical_chf, flag.typical_count) == (Decimal("50.00"), 5)
    assert (found.checked, found.flagged, found.row_ids) == (1, 1, ["BK-BIG"])


async def test_an_amount_needs_three_times_the_median_and_100_above_it() -> None:
    at_three_times = [*_history(median=50.0), _payment("BK-150", "2026-10-10", -150.0)]
    less_than_100_above = [*_history(median=20.0), _payment("BK-99", "2026-10-10", -119.0)]

    assert await _flags(bookings=at_three_times) == {}
    assert await _flags(bookings=less_than_100_above) == {}


async def test_the_median_needs_five_payments_in_the_year_before() -> None:
    old = _payment("BK-OLD", "2025-09-30", -50.0)
    bookings = [*_history(median=50.0, count=4), old, _payment("BK-BIG", "2026-10-10", -500.0)]

    assert await _flags(bookings=bookings) == {}


async def test_a_first_payment_counts_from_100_chf() -> None:
    bookings = [
        _payment("BK-NEW", "2026-10-10", -100.0, counterparty="Schreinerei Binz"),
        _payment("BK-SMALL", "2026-10-11", -99.99, counterparty="Bäckerei Kuhn"),
        # Paid before the period, so not a first payment in it.
        _payment("BK-SEP", "2026-09-02", -300.0, counterparty="Musikschule"),
        _payment("BK-OCT", "2026-10-02", -300.0, counterparty="Musikschule"),
    ]

    assert await _flags(bookings=bookings) == {"BK-NEW": "first_payment"}


async def test_the_second_of_two_equal_payments_on_one_day_is_flagged_from_20_chf() -> None:
    bookings = [
        *_history(median=45.0, counterparty="Coop"),
        _payment("BK-1", "2026-10-10", -45.0, counterparty="Coop"),
        _payment("BK-2", "2026-10-10", -45.0, counterparty="Coop"),
        _payment("BK-3", "2026-10-11", -45.0, counterparty="Coop"),
        *_history(median=19.99, counterparty="Mensa"),
        _payment("BK-4", "2026-10-12", -19.99, counterparty="Mensa"),
        _payment("BK-5", "2026-10-12", -19.99, counterparty="Mensa"),
    ]

    assert await _flags(bookings=bookings) == {"BK-2": "same_day_twice"}


async def test_standing_orders_cash_own_transfers_and_card_bills_are_not_checked() -> None:
    bookings = [
        _booking("BK-SO", "standing_order", -2140.0, counterparty_name="Verwaltung Zürich"),
        _booking("BK-ATM", "atm", -500.0, counterparty_name="Bancomat Zürich HB"),
        _booking("BK-OWN", "account_transfer", -900.0, counterparty_name="Sparkonto"),
        _booking("BK-BILL", "card_settlement", -800.0, counterparty_name="Visa"),
    ]

    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])
    found = await ledger.find_unusual_movements(token=TOKEN, filters=OCTOBER, today=TODAY)

    assert (found.checked, found.flagged) == (0, 0)


async def test_without_a_period_the_last_full_month_is_checked_largest_first() -> None:
    bookings = [
        _payment("BK-SEP", "2026-09-30", -900.0, counterparty="Hotel"),
        _payment("BK-A", "2026-10-03", -150.0, counterparty="Garage"),
        _payment("BK-B", "2026-10-20", -700.0, counterparty="Zahnarzt"),
        _payment("BK-NOV", "2026-11-02", -800.0, counterparty="Schreinerei"),
    ]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])

    found = await ledger.find_unusual_movements(token=TOKEN, filters=Filters(), today=TODAY)

    assert (found.date_from, found.date_to) == (date(2026, 10, 1), date(2026, 10, 31))
    assert [flag.movement.id for flag in found.movements] == ["BK-B", "BK-A"]


async def test_only_10_flags_are_listed_but_all_are_counted() -> None:
    bookings = [
        _payment(f"BK-{index}", "2026-10-10", -100.0 - index, counterparty=f"Shop {index}")
        for index in range(25)
    ]
    ledger = _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])

    found = await ledger.find_unusual_movements(token=TOKEN, filters=OCTOBER, today=TODAY)

    assert (found.flagged, len(found.movements), found.not_listed) == (25, 10, 15)
    assert found.movements[0].movement.id == "BK-24"
    assert len(found.row_ids) == 25


# Restaurant spending in two half years, and a salary that only the later one has.
HALF_YEARS = [
    _booking("BK-A1", "debit_card", -120.0, booking_date="2025-01-14", counterparty_name="Hiltl"),
    _booking("BK-A2", "debit_card", -80.5, booking_date="2025-03-02", counterparty_name="Hiltl"),
    _booking("BK-B1", "debit_card", -150.0, booking_date="2026-02-20", counterparty_name="Hiltl"),
    _booking("BK-B2", "debit_card", -99.5, booking_date="2026-05-09", counterparty_name="Hiltl"),
    _booking("BK-B3", "debit_card", -50.0, booking_date="2026-05-30", counterparty_name="Hiltl"),
    _booking("BK-B4", "salary", 4200.0, booking_date="2026-06-25"),
]


def _half_years() -> LedgerService:
    return _fake_ledger(bookings=HALF_YEARS, purchases=[], statements=[], pages_read=[])


def _compare(first: tuple[str, str], second: tuple[str, str], **filters: Any) -> ComparePeriodsArgs:
    return ComparePeriodsArgs.model_validate(
        {
            "first_from": first[0],
            "first_to": first[1],
            "second_from": second[0],
            "second_to": second[1],
            **filters,
        }
    )


async def test_the_average_counts_a_month_without_a_match_as_zero() -> None:
    filters = Filters(date_from=date(2025, 1, 1), date_to=date(2025, 3, 31), text=["Hiltl"])

    sums = await _half_years().sum_by_month(token=TOKEN, filters=filters, today=TODAY)

    assert sums.money_out_chf == Decimal("-200.5")
    assert sums.average_out_chf == Decimal("-66.83")
    assert sums.month_most_out is not None and sums.month_least_out is not None
    assert (sums.month_most_out.month, sums.month_most_out.money_out_chf) == (
        "2025-01",
        Decimal("-120.0"),
    )
    assert (sums.month_least_out.month, sums.month_least_out.money_out_chf) == (
        "2025-02",
        Decimal(0),
    )
    assert (sums.average_in_chf, sums.month_most_in, sums.month_least_in) == (
        Decimal(0),
        None,
        None,
    )


async def test_two_periods_compare_by_their_sums_and_averages() -> None:
    args = _compare(first=("2025-01-01", "2025-06-30"), second=("2026-01-01", "2026-06-30"))

    comparison = await _half_years().compare_periods(token=TOKEN, args=args, today=TODAY)

    earlier, later = comparison.earlier, comparison.later
    assert (earlier.months, earlier.count, earlier.money_out_chf) == (6, 2, Decimal("-200.5"))
    assert (later.months, later.count, later.money_out_chf) == (6, 4, Decimal("-299.5"))
    assert (earlier.average_out_chf, later.average_out_chf) == (
        Decimal("-33.42"),
        Decimal("-49.92"),
    )
    assert comparison.money_out_change_chf == abs(later.money_out_chf) - abs(earlier.money_out_chf)
    assert comparison.money_out_change_chf == Decimal("99.0")
    assert comparison.money_out_change_percent == Decimal("49.4")
    assert (comparison.money_in_change_chf, comparison.money_in_change_percent) == (
        Decimal("4200.0"),
        None,
    )
    assert comparison.average_out_change_chf == Decimal("16.5")
    assert comparison.average_out_change_percent == Decimal("49.4")
    assert comparison.row_ids == {
        "earlier": ["BK-A1", "BK-A2"],
        "later": ["BK-B1", "BK-B2", "BK-B3", "BK-B4"],
    }


async def test_both_periods_take_the_same_filters() -> None:
    args = _compare(
        first=("2025-01-01", "2025-06-30"), second=("2026-01-01", "2026-06-30"), text="Hiltl"
    )

    comparison = await _half_years().compare_periods(token=TOKEN, args=args, today=TODAY)

    assert comparison.row_ids["later"] == ["BK-B1", "BK-B2", "BK-B3"]
    assert comparison.later.money_in_chf == Decimal(0)


async def test_the_periods_count_by_date_in_whatever_order_they_come() -> None:
    args = _compare(first=("2026-01-01", "2026-06-30"), second=("2025-01-01", "2025-06-30"))

    comparison = await _half_years().compare_periods(token=TOKEN, args=args, today=TODAY)

    assert (comparison.earlier.date_from, comparison.later.date_from) == (
        date(2025, 1, 1),
        date(2026, 1, 1),
    )
    assert comparison.money_out_change_chf == Decimal("99.0")


async def test_a_period_that_ends_before_it_starts_names_its_bounds() -> None:
    with pytest.raises(ValueError, match="second_from is after second_to"):
        _compare(first=("2025-01-01", "2025-06-30"), second=("2026-06-30", "2026-01-01"))
    with pytest.raises(ValueError, match="date_from"):
        _compare(
            first=("2025-01-01", "2025-06-30"),
            second=("2026-01-01", "2026-06-30"),
            date_from="2025-01-01",
        )


async def test_a_period_beyond_the_history_counts_only_the_months_it_covers() -> None:
    args = _compare(first=("2020-01-01", "2025-12-31"), second=("2026-01-01", "2026-12-31"))

    comparison = await _half_years().compare_periods(token=TOKEN, args=args, today=TODAY)

    earlier, later = comparison.earlier, comparison.later
    assert (earlier.date_from, earlier.months, earlier.average_out_chf) == (
        date(2025, 1, 1),
        12,
        Decimal("-16.71"),
    )
    assert (later.date_to, later.months, later.average_out_chf) == (
        date(2026, 6, 30),
        6,
        Decimal("-49.92"),
    )
    assert comparison.average_out_change_chf == Decimal("33.21")


async def test_a_period_outside_the_history_has_no_months_and_no_rows() -> None:
    args = _compare(first=("2019-01-01", "2019-12-31"), second=("2026-01-01", "2026-06-30"))

    comparison = await _half_years().compare_periods(token=TOKEN, args=args, today=TODAY)

    assert (comparison.earlier.months, comparison.earlier.count) == (0, 0)
    assert comparison.row_ids["earlier"] == []


async def test_a_placeholder_instead_of_a_date_points_to_since_salary_start() -> None:
    with pytest.raises(ValueError, match="is not a date.*since_salary_start"):
        _compare(first=("<first_salary_date>", "2025-08-31"), second=("2025-09-01", "2026-11-27"))


def _balanced(booking_id: str, day: str, amount: float, balance: float, name: str) -> dict:
    return _booking(
        booking_id,
        "debit_card" if amount < 0 else "salary",
        amount,
        booking_date=day,
        balance_after=balance,
        counterparty_name=name,
    )


BALANCED = [
    _balanced("BK-01", "2026-09-30", 5000.0, 5000.0, "Arbeitgeber AG"),
    _balanced("BK-02", "2026-10-01", -1000.0, 4000.0, "Vermieter"),
    _balanced("BK-03", "2026-10-02", -20.0, 3980.0, "Migros"),
    _balanced("BK-04", "2026-10-03", -30.0, 3950.0, "Coop"),
    _balanced("BK-05", "2026-10-04", -40.0, 3910.0, "Denner"),
    _balanced("BK-06", "2026-10-05", -50.0, 3860.0, "Lidl"),
    _balanced("BK-07", "2026-10-06", -5.0, 3855.0, "Kiosk"),
    _balanced("BK-08", "2026-10-07", -6.0, 3849.0, "Bäckerei"),
    _balanced("BK-09", "2026-10-25", 5000.0, 8849.0, "Arbeitgeber AG"),
    _balanced("BK-10", "2026-10-25", -500.0, 8349.0, "Vermieter"),
    _balanced("BK-11", "2026-11-02", -100.0, 8249.0, "Migros"),
]


def _balance_args(date_from: str, date_to: str, account_id: str = "ACC-PRIV") -> BalanceChangeArgs:
    return BalanceChangeArgs.model_validate(
        {"account_id": account_id, "date_from": date_from, "date_to": date_to}
    )


async def test_the_parts_of_a_balance_change_add_up_to_it() -> None:
    ledger = _fake_ledger(bookings=BALANCED, purchases=PURCHASES, statements=[], pages_read=[])

    change = await ledger.explain_balance_change(
        token=TOKEN, args=_balance_args(date_from="2026-10-01", date_to="2026-10-31")
    )

    assert (change.start_balance_chf, change.end_balance_chf) == (
        Decimal("5000.0"),
        Decimal("8349.0"),
    )
    assert change.change_chf == Decimal("3349.0")
    assert (change.count, change.money_in_chf, change.money_out_chf) == (
        9,
        Decimal("5000.0"),
        Decimal("-1651.0"),
    )
    assert change.unexplained_chf == 0
    assert [part.counterparty for part in change.largest_out] == [
        "Vermieter",
        "Lidl",
        "Denner",
        "Coop",
        "Migros",
    ]
    assert change.largest_out[0].money_out_chf == Decimal("-1500.0")
    assert change.others_out is not None
    assert (change.others_out.count, change.others_out.money_out_chf) == (2, Decimal("-11.0"))
    assert (change.largest_in[0].counterparty, change.others_in) == ("Arbeitgeber AG", None)
    parts = sum(part.money_out_chf for part in change.largest_out) + change.others_out.money_out_chf
    assert parts == change.money_out_chf
    assert change.row_ids["out"]["Vermieter"] == ["BK-02", "BK-10"]
    assert change.row_ids["out"]["others"] == ["BK-07", "BK-08"]
    assert change.row_ids["in"] == {"Arbeitgeber AG": ["BK-09"]}


async def test_a_balance_change_before_the_first_booking_starts_at_the_opening_balance() -> None:
    ledger = _fake_ledger(bookings=BALANCED, purchases=[], statements=[], pages_read=[])

    change = await ledger.explain_balance_change(
        token=TOKEN, args=_balance_args(date_from="2026-01-01", date_to="2026-09-30")
    )

    assert (change.start_balance_chf, change.end_balance_chf) == (Decimal(0), Decimal("5000.0"))
    assert change.unexplained_chf == 0


async def test_a_balance_that_does_not_add_up_says_by_how_much() -> None:
    gap = [*BALANCED[:2], _balanced("BK-03", "2026-10-02", -20.0, 3900.0, "Migros")]
    ledger = _fake_ledger(bookings=gap, purchases=[], statements=[], pages_read=[])

    change = await ledger.explain_balance_change(
        token=TOKEN, args=_balance_args(date_from="2026-10-01", date_to="2026-10-31")
    )

    assert change.unexplained_chf == Decimal("-80.0")


async def test_an_account_without_bookings_names_the_ones_there_are() -> None:
    ledger = _fake_ledger(bookings=BALANCED, purchases=[], statements=[], pages_read=[])

    with pytest.raises(BadRequestError, match="ACC-NOPE.*ACC-PRIV"):
        await ledger.explain_balance_change(
            token=TOKEN,
            args=_balance_args(date_from="2026-10-01", date_to="2026-10-31", account_id="ACC-NOPE"),
        )


# Student pay, then a salary at a new level from September, and a pro rata 13th salary apart.
CAREER = [
    _booking("BK-S1", "salary", 1690.2, booking_date="2025-06-25"),
    _booking("BK-P1", "debit_card", -400.0, booking_date="2025-07-10"),
    _booking("BK-S2", "salary", 1185.6, booking_date="2025-08-25"),
    _booking("BK-S3", "salary", 5553.64, booking_date="2025-09-25"),
    _booking("BK-P2", "debit_card", -900.0, booking_date="2025-10-04"),
    _booking("BK-S4", "salary", 5553.64, booking_date="2025-10-24"),
    _booking("BK-S5", "salary", 5553.64, booking_date="2025-11-25"),
    _booking("BK-S6", "salary", 1934.61, booking_date="2025-11-25"),
]


def _career(bookings: list[dict] = CAREER) -> LedgerService:
    return _fake_ledger(bookings=bookings, purchases=[], statements=[], pages_read=[])


async def test_since_salary_start_splits_at_the_first_salary_of_todays_level() -> None:
    args = ComparePeriodsArgs.model_validate({"since_salary_start": True, "kind": "spending"})

    comparison = await _career().compare_periods(token=TOKEN, args=args, today=TODAY)

    assert comparison.salary_start == date(2025, 9, 25)
    assert (comparison.earlier.date_from, comparison.earlier.date_to) == (
        date(2025, 6, 1),
        date(2025, 8, 31),
    )
    assert (comparison.later.date_from, comparison.later.date_to) == (
        date(2025, 9, 1),
        date(2025, 11, 30),
    )
    assert (comparison.earlier.average_out_chf, comparison.later.average_out_chf) == (
        Decimal("-133.33"),
        Decimal("-300.0"),
    )
    assert comparison.row_ids == {
        "earlier": ["BK-P1"],
        "later": ["BK-P2"],
        "salary_start": ["BK-S3"],
    }


async def test_since_salary_start_ignores_placeholder_dates() -> None:
    args = ComparePeriodsArgs.model_validate(
        {"since_salary_start": True, "first_from": "<first_salary_date>", "second_to": "today"}
    )

    assert args.first_from is None and args.second_to is None


async def test_a_salary_at_one_level_since_the_history_starts_has_nothing_to_compare() -> None:
    args = ComparePeriodsArgs.model_validate({"since_salary_start": True})

    with pytest.raises(BadRequestError, match="no earlier period"):
        await _career(bookings=CAREER[3:]).compare_periods(token=TOKEN, args=args, today=TODAY)


async def test_without_a_salary_the_customer_is_asked_when_the_job_started() -> None:
    args = ComparePeriodsArgs.model_validate({"since_salary_start": True})

    with pytest.raises(BadRequestError, match="No salary"):
        await _career(bookings=[CAREER[1]]).compare_periods(token=TOKEN, args=args, today=TODAY)


async def test_without_dates_or_since_salary_start_all_four_dates_are_asked_for() -> None:
    with pytest.raises(ValueError, match="all four dates"):
        ComparePeriodsArgs.model_validate({"first_from": "2025-01-01", "first_to": "2025-06-30"})


async def test_a_newest_month_with_only_a_bonus_so_far_keeps_the_split() -> None:
    bonus = _booking("BK-S7", "salary", 800.0, booking_date="2025-12-05")
    args = ComparePeriodsArgs.model_validate({"since_salary_start": "true"})

    comparison = await _career(bookings=[*CAREER, bonus]).compare_periods(
        token=TOKEN, args=args, today=TODAY
    )

    assert comparison.salary_start == date(2025, 9, 25)


TAX_YEAR = [
    _booking("BK-T1", "loan_interest", -227.5, booking_date="2025-03-31", balance_after=9772.5),
    _booking("BK-T2", "loan_interest", -230.0, booking_date="2025-06-30", balance_after=9542.5),
    *[
        _booking(
            f"BK-3A-{month}",
            "standing_order",
            -650.0,
            booking_date=f"2025-{month:02d}-26",
            counterparty_name="Vorsorgekonto Säule 3a",
            balance_after=9542.5 - 650.0 * (month - 6),
        )
        for month in range(7, 13)
    ],
    _booking(
        "BK-3A-IN",
        "standing_order",
        650.0,
        account_id="ACC-3A",
        booking_date="2025-12-26",
        counterparty_name="Privatkonto",
        balance_after=650.0,
    ),
    _booking("BK-T3", "debit_card", -10.0, booking_date="2026-01-05", balance_after=5632.5),
]
CHARGES = [
    {"booking_id": "BK-T1", "loan_id": "LOAN-03", "type": "interest"},
    {"booking_id": "BK-T2", "loan_id": "LOAN-03", "type": "interest"},
]


async def test_a_tax_year_sums_interest_and_3a_and_takes_the_balances_of_31_december(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f"{__name__}.LOAN_CHARGES", CHARGES)
    ledger = _fake_ledger(bookings=TAX_YEAR, purchases=[], statements=[], pages_read=[])

    summary = await ledger.tax_year_summary(
        token=TOKEN, args=TaxYearArgs(year=2025), today=date(2026, 11, 26)
    )

    assert summary.until == date(2025, 12, 31)
    assert summary.mortgage_interest_paid_chf == Decimal("457.5")
    assert summary.row_ids["mortgage_interest"] == ["BK-T1", "BK-T2"]
    assert summary.pillar_3a_paid_chf == Decimal("3900.0")
    assert summary.row_ids["pillar_3a"] == [f"BK-3A-{month}" for month in range(7, 13)]
    assert (summary.pillar_3a_limit_chf, summary.pillar_3a_over_limit_chf) == (Decimal(7258), None)
    assert [(b.account_id, b.date, b.balance_chf) for b in summary.year_end_balances] == [
        ("ACC-3A", date(2025, 12, 26), Decimal("650.0")),
        ("ACC-PRIV", date(2025, 12, 26), Decimal("5642.5")),
    ]
    assert summary.row_ids["ACC-PRIV"] == ["BK-3A-12"]
    assert summary.portfolio_value_chf == Decimal("64165.28")
    assert "not tax advice" in summary.note


async def test_a_year_without_a_loan_has_no_interest_and_3a_over_the_limit_says_by_how_much() -> (
    None
):
    payments = [
        _booking(
            f"BK-P{month}",
            "standing_order",
            -700.0,
            booking_date=f"2025-{month:02d}-26",
            counterparty_name="Vorsorgekonto Säule 3a",
            balance_after=10000.0 - 700.0 * month,
        )
        for month in range(1, 12)
    ]
    ledger = _fake_ledger(bookings=payments, purchases=[], statements=[], pages_read=[])

    summary = await ledger.tax_year_summary(
        token=TOKEN, args=TaxYearArgs(year=2025), today=date(2026, 11, 26)
    )

    assert (summary.mortgage_interest_paid_chf, summary.row_ids["mortgage_interest"]) == (0, [])
    assert summary.pillar_3a_paid_chf == Decimal("7700.0")
    assert summary.pillar_3a_over_limit_chf == Decimal("442.0")


async def test_a_year_that_is_not_over_runs_until_today_and_has_no_year_end_value() -> None:
    ledger = _fake_ledger(bookings=TAX_YEAR, purchases=[], statements=[], pages_read=[])

    summary = await ledger.tax_year_summary(
        token=TOKEN, args=TaxYearArgs(year=2026), today=date(2026, 11, 26)
    )

    assert summary.until == date(2026, 11, 26)
    assert summary.pillar_3a_limit_chf == Decimal(7258)
    assert summary.portfolio_value_chf is None
    assert summary.year_end_balances[-1].balance_chf == Decimal("5632.5")


async def test_a_year_that_has_not_started_is_refused() -> None:
    ledger = _fake_ledger(bookings=TAX_YEAR, purchases=[], statements=[], pages_read=[])

    with pytest.raises(BadRequestError, match="2027 has not started"):
        await ledger.tax_year_summary(
            token=TOKEN, args=TaxYearArgs(year=2027), today=date(2026, 11, 26)
        )


# Jana's first weeks: spending before her first salary on 22 December, and one payment this month.
FIRST_WEEKS = [
    _booking("BK-D1", "debit_card", -835.02, booking_date="2023-12-10"),
    _booking("BK-D2", "salary", 1690.2, booking_date="2023-12-22"),
    _booking("BK-D3", "debit_card", -100.0, booking_date="2026-11-20"),
]


async def test_a_period_covering_part_of_a_month_counts_its_days() -> None:
    ledger = _fake_ledger(bookings=FIRST_WEEKS, purchases=[], statements=[], pages_read=[])
    args = _compare(first=("2023-12-01", "2023-12-21"), second=("2023-12-22", "2026-11-30"))

    comparison = await ledger.compare_periods(token=TOKEN, args=args, today=TODAY)

    earlier, later = comparison.earlier, comparison.later
    assert (earlier.months, earlier.money_out_chf) == (Decimal("0.68"), Decimal("-835.02"))
    assert earlier.average_out_chf == (Decimal("-835.02") * 31 / 21).quantize(Decimal("0.01"))
    # 22 to 31 December is 10/31, January 2024 to October 2026 is 34, November up to today 27/30.
    assert (later.date_to, later.months) == (TODAY, Decimal("35.22"))
    assert later.average_out_chf == Decimal("-2.84")
    assert comparison.average_out_change_chf == Decimal("2.84") - Decimal("1232.65")


async def test_the_current_month_counts_its_days_up_to_today() -> None:
    ledger = _fake_ledger(bookings=FIRST_WEEKS, purchases=[], statements=[], pages_read=[])
    filters = Filters(date_from=date(2026, 11, 1), date_to=date(2026, 11, 30))

    sums = await ledger.sum_by_month(token=TOKEN, filters=filters, today=TODAY)

    assert sums.average_out_chf == (Decimal("-100.0") * 30 / 27).quantize(Decimal("0.01"))
    assert [month.month for month in sums.months] == ["2026-11"]


async def test_two_periods_that_share_a_day_are_refused() -> None:
    with pytest.raises(ValueError, match="share days"):
        _compare(first=("2025-01-01", "2025-06-30"), second=("2025-06-30", "2025-12-31"))
    with pytest.raises(ValueError, match="share days"):
        _compare(first=("2025-03-01", "2025-12-31"), second=("2025-01-01", "2025-06-30"))


async def test_a_settled_bill_without_purchases_counts_as_spending_once(
    statements: list[dict],
) -> None:
    statements.append(
        {
            "statement_id": "STMT-2023-11",
            "card_id": "CARD-VISA",
            "status": "settled",
            "transactions_count": 0,
        }
    )
    old_bill = _booking(
        "BK-9",
        "card_settlement",
        -2264.35,
        reference="STMT-2023-11",
        card_id="CARD-VISA",
        booking_date="2023-12-20",
    )
    ledger = _fake_ledger(
        bookings=[*BOOKINGS, old_bill], purchases=PURCHASES, statements=statements, pages_read=[]
    )

    rows = {row.id: row for row in await ledger.list_rows(token=TOKEN)}

    assert (rows["BK-9"].kind, rows["BK-9"].statement_id) == ("spending", "STMT-2023-11")
    assert rows["BK-5"].kind == "card_settlement"
    december = await ledger.search_movements(
        token=TOKEN,
        args=SearchMovementsArgs(date_from=date(2023, 12, 1), date_to=date(2023, 12, 31)),
    )
    assert (december.row_ids, december.money_out_chf) == (["BK-9"], Decimal("-2264.35"))
