import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from app.clients.banking import BankingClient
from app.core.errors import BadRequestError
from app.core.prompts import load_prompts
from app.features.ledger.schemas import (
    CounterpartySum,
    CounterpartySums,
    Filters,
    Kind,
    LedgerRow,
    MonthSum,
    MonthSums,
    Movement,
    MovementSearch,
    SearchMovementsArgs,
    SumByCounterpartyArgs,
)

PROMPTS = load_prompts(prompts_py=__file__)
PAGE_SIZE = 1000  # the banking API's maximum
OWN_TRANSFER_TYPES = {"account_transfer", "securities_buy"}
# Without a kind, nothing counts twice: no move between own accounts, no card bill.
COUNTED_KINDS: set[Kind] = {"spending", "credit"}
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
            rows=[Movement.model_validate(row, from_attributes=True) for row in listed],
            rows_not_listed=len(rows) - len(listed),
            row_ids=[row.id for row in rows],
        )

    async def sum_by_month(self, token: str, filters: Filters) -> MonthSums:
        """One sum per month of the period, a month without a match as 0."""
        rows = await self._matching(token=token, filters=filters)
        everything = await self.list_rows(token=token)
        by_month: dict[str, list[LedgerRow]] = defaultdict(list)
        for row in rows:
            by_month[row.date.strftime("%Y-%m")].append(row)
        months = _months(filters=filters, rows=everything)
        out, received = _sums(rows=rows)
        return MonthSums(
            count=len(rows),
            money_out_chf=out,
            money_in_chf=received,
            months=[_month_sum(month=month, rows=by_month[month]) for month in months],
            row_ids={month: [row.id for row in by_month[month]] for month in months},
        )

    async def sum_by_counterparty(
        self, token: str, args: SumByCounterpartyArgs
    ) -> CounterpartySums:
        """The counterparties with the largest sums, and the rest as one group."""
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
            counterparties=top,
            others=None if not rest else _counterparty_sum(counterparty="others", rows=rest_rows),
            row_ids={
                group.counterparty: [row.id for row in by_counterparty[group.counterparty]]
                for group in top
            },
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
            purchases = await self._all_pages(
                path=f"/cards/{quote(card['card_id'], safe='')}/transactions", token=token
            )
            rows += [
                _card_row(purchase=purchase, account_id=card["linked_account"])
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


def _counterparty_sum(counterparty: str, rows: list[LedgerRow]) -> CounterpartySum:
    out, received = _sums(rows=rows)
    return CounterpartySum(
        counterparty=counterparty, count=len(rows), money_out_chf=out, money_in_chf=received
    )


def _month_sum(month: str, rows: list[LedgerRow]) -> MonthSum:
    out, received = _sums(rows=rows)
    return MonthSum(month=month, count=len(rows), money_out_chf=out, money_in_chf=received)


def _months(filters: Filters, rows: list[LedgerRow]) -> list[str]:
    # Without a period, from the first to the last row of the ledger.
    if not rows and (filters.date_from is None or filters.date_to is None):
        return []
    first = rows[0].date if filters.date_from is None else filters.date_from
    last = rows[-1].date if filters.date_to is None else filters.date_to
    months, year, month = [], first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
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


def _card_row(purchase: dict[str, Any], account_id: str) -> LedgerRow:
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
    )


def _compact(iban: str) -> str:
    return iban.replace(" ", "").upper()


def _chf(amount: float) -> Decimal:
    # Through str, so 0.1 stays 0.1 and sums add up to the cent.
    return Decimal(str(amount))


def _chf_or_none(amount: float | None) -> Decimal | None:
    return None if amount is None else _chf(amount=amount)
