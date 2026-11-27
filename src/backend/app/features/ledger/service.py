import re
import statistics
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from app.clients.banking import BankingClient
from app.core.errors import BadRequestError
from app.core.prompts import load_prompts
from app.features.ledger.schemas import (
    MIN_TREND_MONTHS,
    CounterpartySum,
    CounterpartySums,
    Filters,
    ForecastMonthsArgs,
    GroupBy,
    GroupSum,
    GroupSums,
    Kind,
    LedgerRow,
    MonthSum,
    MonthSums,
    MonthTrend,
    Movement,
    MovementSearch,
    ProjectedMonth,
    SearchMovementsArgs,
    SumByCounterpartyArgs,
    SumByGroupArgs,
)

PROMPTS = load_prompts(prompts_py=__file__)
PAGE_SIZE = 1000  # the banking API's maximum
OWN_TRANSFER_TYPES = {"account_transfer", "securities_buy"}
# Without a kind, nothing counts twice: no move between own accounts, no card bill.
COUNTED_KINDS: set[Kind] = {"spending", "credit"}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
CENT = Decimal("0.01")
# Every path the model's tools may read; `{}` is one segment. Nothing here changes the bank.
READ_PATHS = [
    "/customer",
    "/accounts",
    "/accounts/{}/balance-preview",
    "/asset-overview",
    "/bookings",
    "/payments",
    "/upcoming-payments",
    "/payees",
    "/standing-orders",
    "/cards",
    "/cards/{}/statements",
    "/cards/{}/transactions",
    "/portfolio",
    "/portfolio/positions",
    "/portfolio/performance",
    "/portfolio/transactions",
    "/loans",
    "/loan-transactions",
    "/fx-rates",
]
# A segment is quoted already; `.` and `..` survive quoting and would climb to another path.
_SEGMENT = r"(?!\.\.?(?:/|$))[^/?#]+"
_READ_PATTERNS = [
    re.compile(_SEGMENT.join(map(re.escape, path.split("{}")))) for path in READ_PATHS
]


class LedgerService:
    def __init__(self, banking: BankingClient) -> None:
        self.banking = banking
        # One instance per request, so a turn with several ledger tools reads the bank once.
        self._rows: dict[str, list[LedgerRow]] = {}

    async def read(self, path: str, token: str, params: dict[str, Any] | None = None) -> Any:
        """One read from the banking API as the customer, only on a path of `READ_PATHS`."""
        if not any(pattern.fullmatch(path) for pattern in _READ_PATTERNS):
            raise BadRequestError(f"{path} is not a read the bank data allows")
        return await self.banking.get(path=path, token=token, params=params)

    async def get_today(self) -> date:
        """The e-banking's date, which the demo data ends on; the server clock may differ."""
        info = await self.banking.get(path="/system/info")
        return date.fromisoformat(info["today"])

    async def list_rows(self, token: str) -> list[LedgerRow]:
        """Every booking and credit card purchase of the customer, oldest first."""
        if token not in self._rows:
            self._rows[token] = await self._read_rows(token=token)
        return self._rows[token]

    async def search_movements(self, token: str, args: SearchMovementsArgs) -> MovementSearch:
        """The rows that match, with their count and sums, newest or largest first."""
        rows = await self._matching(token=token, filters=args)
        if args.sort == "largest":
            listed = sorted(rows, key=lambda row: abs(row.amount_chf), reverse=True)
        else:
            listed = sorted(rows, key=lambda row: (row.date, row.id), reverse=args.sort == "newest")
        listed = listed[: args.limit]
        out, received = _sums(rows=rows)
        return MovementSearch(
            count=len(rows),
            money_out_chf=out,
            money_in_chf=received,
            **_provisional(rows=rows),
            rows=[Movement.model_validate(row, from_attributes=True) for row in listed],
            rows_not_listed=len(rows) - len(listed),
            row_ids=[row.id for row in rows],
        )

    async def sum_by_month(self, token: str, filters: Filters) -> MonthSums:
        """One sum per month of the period, a month without a match as 0."""
        rows = await self._matching(token=token, filters=filters)
        everything = await self.list_rows(token=token)
        by_month = _by_month(rows=rows)
        months = _months(filters=filters, rows=everything)
        out, received = _sums(rows=rows)
        return MonthSums(
            count=len(rows),
            money_out_chf=out,
            money_in_chf=received,
            **_provisional(rows=rows),
            months=[_month_sum(month=month, rows=by_month[month]) for month in months],
            row_ids={month: [row.id for row in by_month[month]] for month in months},
        )

    async def sum_by_counterparty(
        self, token: str, args: SumByCounterpartyArgs
    ) -> CounterpartySums:
        """The counterparties that moved the most money, in and out, and the rest as one group."""
        rows = await self._matching(token=token, filters=args)
        by_counterparty: dict[str, list[LedgerRow]] = defaultdict(list)
        for row in rows:
            by_counterparty[row.counterparty or row.text].append(row)
        groups = sorted(
            (
                _counterparty_sum(counterparty=name, rows=group)
                for name, group in by_counterparty.items()
            ),
            key=lambda group: group.money_in_chf - group.money_out_chf,
            reverse=True,
        )
        top, rest = groups[: args.limit], groups[args.limit :]
        rest_rows = [row for group in rest for row in by_counterparty[group.counterparty]]
        out, received = _sums(rows=rows)
        return CounterpartySums(
            count=len(rows),
            money_out_chf=out,
            money_in_chf=received,
            **_provisional(rows=rows),
            counterparties=top,
            others=None if not rest else _counterparty_sum(counterparty="others", rows=rest_rows),
            row_ids={
                **{
                    group.counterparty: [row.id for row in by_counterparty[group.counterparty]]
                    for group in top
                },
                **({} if not rest else {"others": [row.id for row in rest_rows]}),
            },
        )

    async def forecast_months(
        self, token: str, args: ForecastMonthsArgs, today: date
    ) -> MonthTrend:
        """A straight line through the last full months, and where it leads in the next ones."""
        everything = await self.list_rows(token=token)
        # The current month isn't over, so its low sum would bend the line.
        last_day = today.replace(day=1) - timedelta(days=1)
        first_day = _month_start(month=_shift(month=_month(day=last_day), by=1 - args.months_back))
        if everything:
            # The bank's history covers whole months, so the first booking's month counts in full.
            first_day = max(first_day, everything[0].date.replace(day=1))
        # A history that starts this month leaves first_day after last_day: no month at all.
        months_covered = (
            0
            if not everything or first_day > last_day
            else _count_months(first=first_day, last=last_day)
        )
        if months_covered < MIN_TREND_MONTHS:
            raise BadRequestError(PROMPTS["not_enough_months"].format(months=months_covered))
        filters = Filters(
            **args.model_dump(exclude={"months_back", "months_ahead"}),
            date_from=first_day,
            date_to=last_day,
        )
        months = _months(filters=filters, rows=everything)
        by_month = _by_month(rows=await self._matching(token=token, filters=filters))
        sums = [_month_sum(month=month, rows=by_month[month]) for month in months]
        nets = [month.money_out_chf + month.money_in_chf for month in sums]
        slope, intercept = statistics.linear_regression(range(len(nets)), [float(n) for n in nets])
        average = (sum(nets, Decimal(0)) / len(nets)).quantize(CENT)
        trend = _cents(value=slope)
        return MonthTrend(
            first_month=months[0],
            last_month=months[-1],
            months_used=len(months),
            average_chf=average,
            trend_chf_per_month=trend,
            trend_percent_per_month=None
            if average == 0
            else (trend / abs(average) * 100).quantize(CENT),
            projection=[
                ProjectedMonth(
                    month=_shift(month=months[-1], by=ahead),
                    trend_chf=_cents(value=intercept + slope * (len(nets) - 1 + ahead)),
                    average_chf=average,
                )
                for ahead in range(1, args.months_ahead + 1)
            ],
            months=sums,
            row_ids={month: [row.id for row in by_month[month]] for month in months},
        )

    async def sum_by_group(self, token: str, args: SumByGroupArgs) -> GroupSums:
        """The matching movements added up per quarter, year, weekday, account or kind."""
        rows = await self._matching(token=token, filters=args)
        grouped: dict[str, list[LedgerRow]] = defaultdict(list)
        for row in rows:
            grouped[_group(row=row, group_by=args.group_by)].append(row)
        # Every weekday, so a day without spending shows as 0 next to the others.
        names = WEEKDAYS if args.group_by == "weekday" else sorted(grouped)
        out, received = _sums(rows=rows)
        groups = []
        for name in names:
            group_out, group_in = _sums(rows=grouped[name])
            groups.append(
                GroupSum(
                    group=name,
                    count=len(grouped[name]),
                    money_out_chf=group_out,
                    money_in_chf=group_in,
                )
            )
        return GroupSums(
            count=len(rows),
            money_out_chf=out,
            money_in_chf=received,
            groups=groups,
            row_ids={name: [row.id for row in grouped[name]] for name in names},
        )

    async def _matching(self, token: str, filters: Filters) -> list[LedgerRow]:
        rows = await self.list_rows(token=token)
        # A word no movement contains is a category the model made up, not an empty period.
        if filters.text is not None and not any(
            _has_words(row=row, words=filters.text) for row in rows
        ):
            words = ", ".join(f'"{word}"' for word in filters.text)
            raise BadRequestError(PROMPTS["text_not_found"].format(words=words))
        return [row for row in rows if _matches(row=row, filters=filters)]

    async def _read_rows(self, token: str) -> list[LedgerRow]:
        accounts = await self.read(path="/accounts", token=token)
        own_ibans = {_compact(iban=account["iban"]) for account in accounts["items"]}
        charges = await self.read(path="/loan-transactions", token=token)
        charge_by_booking = {charge["booking_id"]: charge for charge in charges["items"]}

        rows = [
            _booking_row(
                booking=booking,
                own_ibans=own_ibans,
                loan_charge=charge_by_booking.get(booking["booking_id"]),
            )
            for booking in await self._all_pages(path="/bookings", token=token)
        ]
        cards = await self.read(path="/cards", token=token)
        for card in cards["items"]:
            # Debit card payments are bookings already; only a credit card has its own list.
            if card["type"] != "credit":
                continue
            card_path = f"/cards/{quote(card['card_id'], safe='')}"
            statements = await self.read(path=f"{card_path}/statements", token=token)
            open_statements = {
                statement["statement_id"]
                for statement in statements["items"]
                if statement["status"] == "open"
            }
            purchases = await self._all_pages(path=f"{card_path}/transactions", token=token)
            rows += [
                _card_row(
                    purchase=purchase,
                    account_id=card["linked_account"],
                    open_statements=open_statements,
                )
                for purchase in purchases
            ]
        return sorted(rows, key=lambda row: (row.date, row.id))

    async def _all_pages(self, path: str, token: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            page = await self.read(
                path=path, token=token, params={"limit": PAGE_SIZE, "offset": len(items)}
            )
            items += page["items"]
            if len(items) >= page["total"] or not page["items"]:
                return items


def _matches(row: LedgerRow, filters: Filters) -> bool:
    kinds = COUNTED_KINDS if filters.kind is None else set(filters.kind)
    amount = abs(row.amount_chf)
    checks = [
        row.kind in kinds,
        filters.date_from is None or row.date >= filters.date_from,
        filters.date_to is None or row.date <= filters.date_to,
        filters.text is None or _has_words(row=row, words=filters.text),
        filters.account_id is None or row.account_id == filters.account_id,
        filters.card_id is None or row.card_id == filters.card_id,
        filters.amount_min is None or amount >= filters.amount_min,
        filters.amount_max is None or amount <= filters.amount_max,
    ]
    return all(checks)


def _has_words(row: LedgerRow, words: list[str]) -> bool:
    # At the start of a word, so "rent" does not find "Parentis".
    searched = f"{row.text} {row.counterparty or ''}"
    return any(re.search(rf"\b{re.escape(word)}", searched, re.IGNORECASE) for word in words)


def _sums(rows: Iterable[LedgerRow]) -> tuple[Decimal, Decimal]:
    amounts = [row.amount_chf for row in rows]
    out = sum((amount for amount in amounts if amount < 0), Decimal(0))
    received = sum((amount for amount in amounts if amount > 0), Decimal(0))
    return out, received


def _provisional(rows: Iterable[LedgerRow]) -> dict[str, Decimal]:
    out, received = _sums(rows=(row for row in rows if row.provisional))
    return {"provisional_out_chf": out, "provisional_in_chf": received}


def _counterparty_sum(counterparty: str, rows: list[LedgerRow]) -> CounterpartySum:
    out, received = _sums(rows=rows)
    return CounterpartySum(
        counterparty=counterparty, count=len(rows), money_out_chf=out, money_in_chf=received
    )


def _month_sum(month: str, rows: list[LedgerRow]) -> MonthSum:
    out, received = _sums(rows=rows)
    return MonthSum(
        month=month,
        count=len(rows),
        money_out_chf=out,
        money_in_chf=received,
        **_provisional(rows=rows),
    )


def _by_month(rows: list[LedgerRow]) -> dict[str, list[LedgerRow]]:
    by_month: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in rows:
        by_month[_month(day=row.date)].append(row)
    return by_month


def _group(row: LedgerRow, group_by: GroupBy) -> str:
    match group_by:
        case "quarter":
            return f"{row.date.year}-Q{(row.date.month - 1) // 3 + 1}"
        case "year":
            return str(row.date.year)
        case "weekday":
            return WEEKDAYS[row.date.weekday()]
        case "account":
            return row.account_id
        case "kind":
            return row.kind


def _month(day: date) -> str:
    return day.strftime("%Y-%m")


def _month_start(month: str) -> date:
    return date.fromisoformat(f"{month}-01")


def _shift(month: str, by: int) -> str:
    index = int(month[:4]) * 12 + int(month[5:]) - 1 + by
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _cents(value: float) -> Decimal:
    # Through str, so the float's last digits don't end up in the figure.
    return Decimal(str(round(value, 2))).quantize(CENT)


def _count_months(first: date, last: date) -> int:
    return (last.year - first.year) * 12 + last.month - first.month + 1


def _months(filters: Filters, rows: list[LedgerRow]) -> list[str]:
    # Without a period, from the first to the last row of the ledger.
    if not rows and (filters.date_from is None or filters.date_to is None):
        return []
    first = rows[0].date if filters.date_from is None else filters.date_from
    last = rows[-1].date if filters.date_to is None else filters.date_to
    months = [_month(day=first)]
    while months[-1] < _month(day=last):
        months.append(_shift(month=months[-1], by=1))
    return months


def _booking_row(
    booking: dict[str, Any], own_ibans: set[str], loan_charge: dict[str, Any] | None
) -> LedgerRow:
    is_settlement = booking["transaction_type"] == "card_settlement"
    return LedgerRow(
        source="booking",
        id=booking["booking_id"],
        account_id=booking["account_id"],
        card_id=booking.get("card_id"),
        date=booking["booking_date"],
        amount_chf=_chf(amount=booking["amount"]),
        text=booking["booking_text"],
        counterparty=booking.get("counterparty_name"),
        transaction_type=booking["transaction_type"],
        original_amount=_chf_or_none(amount=booking.get("original_amount")),
        original_currency=booking.get("original_currency"),
        # The bank puts the statement id of a card bill into the reference.
        statement_id=booking.get("reference") if is_settlement else None,
        loan_id=None if loan_charge is None else loan_charge["loan_id"],
        loan_charge=None if loan_charge is None else loan_charge["type"],
        kind=_booking_kind(booking=booking, own_ibans=own_ibans),
    )


def _booking_kind(booking: dict[str, Any], own_ibans: set[str]) -> Kind:
    if booking["transaction_type"] == "card_settlement":
        return "card_settlement"
    iban = booking.get("counterparty_iban")
    to_own_account = iban is not None and _compact(iban=iban) in own_ibans
    if booking["transaction_type"] in OWN_TRANSFER_TYPES or to_own_account:
        return "own_transfer"
    return "credit" if booking["amount"] > 0 else "spending"


def _card_row(purchase: dict[str, Any], account_id: str, open_statements: set[str]) -> LedgerRow:
    # The card lists a charge as positive; the ledger uses the sign of a booking.
    amount = -_chf(amount=purchase["amount_chf"])
    original = _chf_or_none(amount=purchase.get("original_amount"))
    return LedgerRow(
        source="card_transaction",
        id=purchase["card_transaction_id"],
        account_id=account_id,
        card_id=purchase["card_id"],
        date=purchase["transaction_date"],
        amount_chf=amount,
        text=purchase["merchant_text"],
        counterparty=purchase.get("merchant_name"),
        original_amount=None if original is None else -original,
        original_currency=purchase.get("original_currency"),
        statement_id=purchase.get("statement_id"),
        kind="credit" if amount > 0 else "spending",
        provisional=purchase.get("statement_id") in open_statements,
    )


def _compact(iban: str) -> str:
    return iban.replace(" ", "").upper()


def _chf(amount: float) -> Decimal:
    # Through str, so 0.1 stays 0.1 and sums add up to the cent.
    return Decimal(str(amount))


def _chf_or_none(amount: float | None) -> Decimal | None:
    return None if amount is None else _chf(amount=amount)
