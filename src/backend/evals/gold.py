"""Gold figures: computed from the banking API, checked a second way, frozen once written."""

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.core.tools import Tool
from app.features.accounts import tools as account_tools
from app.features.accounts.service import AccountService
from app.features.bank_data import tools as bank_data_tools
from app.features.bank_data.service import BankDataService
from app.features.figure_checks.service import _figures, _found
from app.features.ledger import tools as ledger_tools
from app.features.ledger.service import LedgerService
from evals import reference
from evals.run import ExpectedCall

GOLD_PATH = Path(__file__).with_name("gold.yaml")
# Written by this module, never by hand; a value once here is never changed.
FROZEN_PATH = Path(__file__).with_name("gold_figures.json")
CUSTOMERS = {
    "lukas": "lukas2026",
    "jana": "jana2026",
    "daniela": "daniela2026",
    "marco": "marco2026",
}
PAGE_SIZE = 1000
CENT = Decimal("0.01")
OWN_TRANSFER_TYPES = {"account_transfer", "securities_buy"}

Source = Literal["ledger", "bookings", "card", "accounts", "loans", "upcoming"]
# original: the foreign amounts as written, fee: the card's fx fee; both only for decoys.
Measure = Literal["out", "in", "net", "count", "sum", "original", "fee"]
Kind = Literal["spending", "credit", "own_transfer", "card_settlement"]
Failure = Literal[
    "invented_figure",
    "sum_in_answer",
    "double_counting",
    "wrong_sign",
    "wrong_currency",
    "wrong_date_range",
    "in_source_but_wrong",
    "check_missed_wrong_figure",
    "check_flagged_right_figure",
    "no_figure",
]


class Spec(BaseModel):
    """Which rows a figure adds up and how; the same filters on every path."""

    model_config = ConfigDict(extra="forbid")

    source: Source
    measure: Measure = "out"
    date_from: date | None = None
    date_to: date | None = None
    # Words at the start of a word in the text or counterparty, any of them, ignoring case.
    text: list[str] = Field(default_factory=list)
    # Ledger only: the kinds the app's tools count without a kind filter.
    kind: list[Kind] = Field(default_factory=lambda: ["spending", "credit"])
    # transaction_type for bookings, interest or amortisation for loans.
    type: list[str] = Field(default_factory=list)
    account: list[str] = Field(default_factory=list)
    card: str | None = None


class Term(Spec):
    """A figure built from several specs: its own rows, plus and minus these."""

    plus: list[Spec] = Field(default_factory=list)
    minus: list[Spec] = Field(default_factory=list)


class GoldFigure(Term):
    name: str
    # Figures of one group are alternatives: any one of them answers it.
    group: str | None = None
    # False: a right figure the answer may show without having to.
    required: bool = True

    @property
    def group_name(self) -> str:
        return self.name if self.group is None else self.group


class Decoy(Term):
    name: str
    failure: Failure


class ExampleCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class GoldQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer: str
    question: str
    category: str
    split: Literal["tune", "held_out"]
    # The same question asked of several customers; a template stays on one side of the split.
    template: str | None = None
    # Any one set answers the question; extra calls are allowed.
    call_sets: list[list[ExpectedCall]]
    not_called: list[str] = Field(default_factory=list)
    # Concrete calls of a right path, run without the model to prove the figures are reachable.
    example: list[ExampleCall]
    figures: list[GoldFigure] = Field(default_factory=list)
    decoys: list[Decoy] = Field(default_factory=list)
    traps: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Row:
    id: str
    date: date
    # Negative is money out, for card purchases too; positive for loan charges and due payments.
    amount: Decimal
    text: str
    kind: Kind | None = None
    type: str | None = None
    account: str | None = None
    card: str | None = None
    original: Decimal | None = None
    fee: Decimal | None = None


@dataclass(frozen=True)
class Value:
    value: Decimal
    count: int
    ids: list[str]
    # The amounts of those rows, without sign: figures an answer may show beside the total.
    amounts: list[Decimal] = field(default_factory=list)


@dataclass
class Bank:
    """One customer's data as the banking API returns it."""

    ledger: list[Row]
    bookings: list[Row]
    cards: list[Row]
    accounts: list[Row]
    loans: list[Row]
    upcoming: list[Row]


def chf(amount: float | str | Decimal) -> Decimal:
    return Decimal(str(amount)).quantize(CENT)


def compact(iban: str | None) -> str:
    return (iban or "").replace(" ", "").upper()


def has_words(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}", text, re.IGNORECASE) for word in words)


def booking_kind(booking: dict[str, Any], own_ibans: set[str]) -> Kind:
    if booking["transaction_type"] == "card_settlement":
        return "card_settlement"
    is_own = compact(iban=booking.get("counterparty_iban")) in own_ibans
    if booking["transaction_type"] in OWN_TRANSFER_TYPES or is_own:
        return "own_transfer"
    return "credit" if Decimal(str(booking["amount"])) > 0 else "spending"


def booking_row(booking: dict[str, Any], own_ibans: set[str]) -> Row:
    return Row(
        id=booking["booking_id"],
        date=date.fromisoformat(booking["booking_date"]),
        amount=chf(amount=booking["amount"]),
        text=f"{booking['booking_text']} {booking.get('counterparty_name') or ''}",
        kind=booking_kind(booking=booking, own_ibans=own_ibans),
        type=booking["transaction_type"],
        account=booking["account_id"],
        card=booking.get("card_id"),
        original=_or_none(amount=booking.get("original_amount")),
    )


def card_row(purchase: dict[str, Any], account: str | None) -> Row:
    # The card lists a charge as positive and a refund as negative.
    amount = -chf(amount=purchase["amount_chf"])
    return Row(
        id=purchase["card_transaction_id"],
        date=date.fromisoformat(purchase["transaction_date"]),
        amount=amount,
        text=f"{purchase['merchant_text']} {purchase.get('merchant_name') or ''}",
        kind="credit" if amount > 0 else "spending",
        type="card_purchase",
        account=account,
        card=purchase["card_id"],
        original=_or_none(amount=purchase.get("original_amount")),
        fee=_or_none(amount=purchase.get("fx_fee_chf")),
    )


def _or_none(amount: float | str | None) -> Decimal | None:
    return None if amount is None or amount == "" else chf(amount=amount)


def matches(row: Row, spec: Spec) -> bool:
    checks = [
        spec.date_from is None or row.date >= spec.date_from,
        spec.date_to is None or row.date <= spec.date_to,
        not spec.text or has_words(text=row.text, words=spec.text),
        not spec.type or row.type in spec.type,
        not spec.account or row.account in spec.account,
        spec.card is None or row.card == spec.card,
        spec.source != "ledger" or row.kind in spec.kind,
    ]
    return all(checks)


def measure(rows: list[Row], how: Measure) -> Value:
    amounts = [row.amount for row in rows]
    totals: dict[Measure, Decimal] = {
        "out": -sum((amount for amount in amounts if amount < 0), Decimal(0)),
        "in": sum((amount for amount in amounts if amount > 0), Decimal(0)),
        "net": -sum(amounts, Decimal(0)),
        "count": Decimal(len(rows)),
        "sum": sum(amounts, Decimal(0)),
        "original": sum((abs(row.original or Decimal(0)) for row in rows), Decimal(0)),
        "fee": sum((row.fee or Decimal(0) for row in rows), Decimal(0)),
    }
    counted = rows
    if how == "out":
        counted = [row for row in rows if row.amount < 0]
    if how == "in":
        counted = [row for row in rows if row.amount > 0]
    return Value(
        value=totals[how],
        count=len(counted),
        ids=[row.id for row in counted],
        amounts=[abs(row.amount) for row in counted],
    )


def rows_of(bank: Bank, source: Source) -> list[Row]:
    by_source: dict[Source, list[Row]] = {
        "ledger": bank.ledger,
        "bookings": bank.bookings,
        "card": bank.cards,
        "accounts": bank.accounts,
        "loans": bank.loans,
        "upcoming": bank.upcoming,
    }
    return by_source[source]


def evaluate(spec: Spec, rows: list[Row]) -> Value:
    return measure(rows=[row for row in rows if matches(row=row, spec=spec)], how=spec.measure)


def parts(term: Term) -> list[tuple[int, Spec]]:
    own = Spec.model_validate(
        term.model_dump(exclude={"plus", "minus", "name", "group", "required", "failure"})
    )
    return [(1, own), *[(1, spec) for spec in term.plus], *[(-1, spec) for spec in term.minus]]


def evaluate_term(term: Term, bank: "Bank") -> Value:
    values = [
        (sign, evaluate(spec=spec, rows=rows_of(bank=bank, source=spec.source)))
        for sign, spec in parts(term=term)
    ]
    return Value(
        value=sum((sign * value.value for sign, value in values), Decimal(0)),
        count=sum(value.count for _, value in values),
        ids=[row_id for _, value in values for row_id in value.ids],
        amounts=[amount for _, value in values for amount in value.amounts],
    )


class _TextDates(yaml.SafeLoader):
    """Leaves dates as text, so call set patterns such as 2026-10-01 stay strings."""


_TextDates.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_gold(path: Path = GOLD_PATH) -> list[GoldQuestion]:
    content = yaml.load(path.read_text(), Loader=_TextDates)  # noqa: S506
    return [GoldQuestion.model_validate(item) for item in content["questions"]]


def load_frozen(path: Path = FROZEN_PATH) -> dict[str, dict[str, dict[str, Any]]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def freeze(
    frozen: dict[str, dict[str, dict[str, Any]]], question_id: str, name: str, value: Value
) -> str | None:
    """Adds a new value; returns the problem when it would change a frozen one."""
    entry = {"value": str(value.value), "count": value.count}
    current = frozen.setdefault(question_id, {}).get(name)
    if current is None:
        frozen[question_id][name] = entry
        return None
    if current == entry:
        return None
    return f"{question_id}/{name}: frozen {current}, now {entry}. Investigate, never refreeze."


class BankReader:
    """Reads one customer's data straight from the banking API, without the app's ledger."""

    def __init__(self, client: httpx.AsyncClient, base_url: str, token: str) -> None:
        self.client = client
        self.base_url = base_url
        self.token = token

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self.client.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        response.raise_for_status()
        return response.json()

    async def all_pages(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        items: list[Any] = []
        while True:
            page = await self.get(
                path=path, params={**(params or {}), "limit": PAGE_SIZE, "offset": len(items)}
            )
            items += page["items"]
            if len(items) >= page["total"] or not page["items"]:
                return items

    async def read(self) -> Bank:
        accounts = (await self.get(path="/accounts"))["items"]
        own_ibans = {compact(iban=account["iban"]) for account in accounts}
        bookings = [
            booking_row(booking=booking, own_ibans=own_ibans)
            for booking in await self.all_pages(path="/bookings")
        ]
        cards: list[Row] = []
        for card in (await self.get(path="/cards"))["items"]:
            if card["type"] != "credit":
                continue
            purchases = await self.all_pages(
                path=f"/cards/{quote(card['card_id'], safe='')}/transactions"
            )
            cards += [
                card_row(purchase=purchase, account=card.get("linked_account"))
                for purchase in purchases
            ]
        loans = [
            Row(
                id=charge["booking_id"],
                date=date.fromisoformat(charge["value_date"]),
                amount=chf(amount=charge["amount"]),
                text=charge["loan_id"],
                type=charge["type"],
                account=charge["debit_account_id"],
            )
            for charge in (await self.get(path="/loan-transactions"))["items"]
        ]
        upcoming = [
            upcoming_row(item=item)
            for item in (await self.get(path="/upcoming-payments", params={"to": "2027-12-31"}))[
                "items"
            ]
        ]
        return Bank(
            ledger=bookings + cards,
            bookings=bookings,
            cards=cards,
            accounts=[account_row(account=account) for account in accounts],
            loans=loans,
            upcoming=upcoming,
        )


def account_row(account: dict[str, Any]) -> Row:
    return Row(
        id=account["account_id"],
        date=date.fromisoformat(account["balance_date"]),
        amount=chf(amount=account["current_balance"]),
        text=account["name"],
        type=account["type"],
        account=account["account_id"],
    )


def upcoming_row(item: dict[str, Any]) -> Row:
    return Row(
        id=f"{item['due_date']} {item['source_id']}",
        date=date.fromisoformat(item["due_date"]),
        amount=chf(amount=item["amount"]),
        text=f"{item['payee_name']} {item.get('description') or ''}",
        type=item["type"],
        account=item["debit_account_id"],
    )


class SecondPath:
    """The same figure another way: the seed CSVs through evals.reference, or the bank's sums."""

    def __init__(self, reader: BankReader, folder: Path) -> None:
        self.reader = reader
        self.folder = folder

    async def check(self, spec: Spec, value: Value) -> str | None:
        """None when the second path agrees; otherwise what differs."""
        name, other = await self.compute(spec=spec)
        if other.value == value.value and sorted(other.ids) == sorted(value.ids):
            return None
        missing = sorted(set(value.ids) - set(other.ids))[:5]
        extra = sorted(set(other.ids) - set(value.ids))[:5]
        return (
            f"{name} says {other.value} ({other.count} rows), the API path {value.value}"
            f" ({value.count} rows); only in API path: {missing}, only in {name}: {extra}"
        )

    async def compute(self, spec: Spec) -> tuple[str, Value]:
        if spec.source == "ledger" and spec.card is not None:
            return "bank card sum", await self.card(spec=spec)
        if spec.source == "ledger":
            return "evals.reference movements", self.reference(spec=spec)
        if spec.source == "card":
            return "bank card sum", await self.card(spec=spec)
        if spec.source == "bookings":
            return "bank booking sums", await self.bookings(spec=spec)
        if spec.source == "accounts":
            return "seed accounts, opening balance plus bookings", self.accounts(spec=spec)
        if spec.source == "loans":
            return "bank loan sum", await self.loans(spec=spec)
        return "seed upcoming payments", self.upcoming(spec=spec)

    def reference(self, spec: Spec) -> Value:
        # Its own rules for own transfers, card bills and refunds, read from the seed CSVs.
        if spec.account or spec.type or set(spec.kind) - {"spending", "credit"}:
            raise ValueError("evals.reference has no account, type or own transfer filter")
        if spec.measure not in ("out", "count"):
            raise ValueError("evals.reference counts spending only, use measure out or count")
        movements = reference.read_movements(folder=self.folder)
        rows = [
            Row(
                id=movement.id,
                date=date.fromisoformat(movement.date),
                amount=chf(amount=movement.amount),
                text=movement.text,
            )
            for movement in movements
        ]
        picked = [row for row in rows if _in_period_with_words(row=row, spec=spec)]
        if spec.measure == "count":
            spent = [row for row in picked if row.amount < 0]
            return Value(value=Decimal(len(spent)), count=len(spent), ids=[r.id for r in spent])
        return measure(rows=picked, how="out")

    async def card(self, spec: Spec) -> Value:
        card = spec.card or "CARD-VISA"
        items: dict[str, dict[str, Any]] = {}
        for word in spec.text or [None]:
            params = _period_params(spec=spec) | ({} if word is None else {"q": word})
            page = await self.reader.get(
                path=f"/cards/{quote(card, safe='')}/transactions",
                params=params | {"limit": PAGE_SIZE},
            )
            if page["total"] > PAGE_SIZE:
                raise ValueError("narrow the card figure, the bank returned more than one page")
            if word is None and chf(amount=page["sum_chf"]) != chf(
                amount=sum((chf(amount=item["amount_chf"]) for item in page["items"]), Decimal(0))
            ):
                raise ValueError(f"the bank's sum_chf of {card} disagrees with its own rows")
            items |= {item["card_transaction_id"]: item for item in page["items"]}
        rows = [card_row(purchase=item, account=None) for item in items.values()]
        if spec.source == "ledger":
            rows = [row for row in rows if row.kind in spec.kind]
        return measure(rows=rows, how=spec.measure)

    async def bookings(self, spec: Spec) -> Value:
        direction = {"out": "debit", "in": "credit"}.get(spec.measure)
        items: dict[str, dict[str, Any]] = {}
        for word in spec.text or [None]:
            for kind in spec.type or [None]:
                for account in spec.account or [None]:
                    params: dict[str, Any] = _period_params(spec=spec)
                    params |= {} if word is None else {"q": word}
                    params |= {} if kind is None else {"transaction_type": kind}
                    params |= {} if account is None else {"account": account}
                    params |= {} if direction is None else {"direction": direction}
                    page = await self.reader.get(path="/bookings", params=params | {"limit": 1000})
                    if page["total"] > PAGE_SIZE:
                        raise ValueError("narrow the booking figure, more than one page")
                    total = chf(amount=page["sum_credit"]) + chf(amount=page["sum_debit"])
                    listed = sum((chf(amount=item["amount"]) for item in page["items"]), Decimal(0))
                    if total != listed:
                        raise ValueError(f"the bank's sums for {params} disagree with its rows")
                    items |= {item["booking_id"]: item for item in page["items"]}
        rows = [booking_row(booking=item, own_ibans=set()) for item in items.values()]
        return measure(rows=rows, how=spec.measure)

    def accounts(self, spec: Spec) -> Value:
        rows = reference.read_rows(folder=self.folder, name="accounts")
        bookings = reference.read_rows(folder=self.folder, name="bookings")
        picked = [row for row in rows if not spec.account or row["account_id"] in spec.account]
        total = Decimal(0)
        for account in picked:
            booked = sum(
                (
                    chf(amount=b["amount"])
                    for b in bookings
                    if b["account_id"] == account["account_id"]
                ),
                Decimal(0),
            )
            computed = chf(amount=account["opening_balance"]) + booked
            if computed != chf(amount=account["current_balance"]):
                raise ValueError(f"{account['account_id']}: opening plus bookings is {computed}")
            total += computed
        return Value(value=total, count=len(picked), ids=[row["account_id"] for row in picked])

    async def loans(self, spec: Spec) -> Value:
        params = _period_params(spec=spec)
        if len(spec.type) == 1:
            params["type"] = spec.type[0]
        page = await self.reader.get(path="/loan-transactions", params=params)
        csv_rows = [
            row
            for row in reference.read_rows(folder=self.folder, name="loan_transactions")
            if (not spec.type or row["type"] in spec.type)
            and _within(day=date.fromisoformat(row["value_date"]), spec=spec)
        ]
        csv_sum = sum((chf(amount=row["amount"]) for row in csv_rows), Decimal(0))
        if chf(amount=page["sum_chf"]) != csv_sum:
            raise ValueError(f"loan sum_chf {page['sum_chf']} disagrees with the seed's {csv_sum}")
        return Value(
            value=csv_sum, count=len(csv_rows), ids=[row["booking_id"] for row in csv_rows]
        )

    def upcoming(self, spec: Spec) -> Value:
        rows = [
            Row(
                id=f"{row['due_date']} {row['source_id']}",
                date=date.fromisoformat(row["due_date"]),
                amount=chf(amount=row["amount"]),
                text=f"{row['payee_name']} {row['description']}",
                type=row["type"],
                account=row["debit_account_id"],
            )
            for row in reference.read_rows(folder=self.folder, name="upcoming_payments")
        ]
        return evaluate(spec=spec, rows=rows)


def _within(day: date, spec: Spec) -> bool:
    return (spec.date_from is None or day >= spec.date_from) and (
        spec.date_to is None or day <= spec.date_to
    )


def _in_period_with_words(row: Row, spec: Spec) -> bool:
    return _within(day=row.date, spec=spec) and (
        not spec.text or has_words(text=row.text, words=spec.text)
    )


def _period_params(spec: Spec) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if spec.date_from is not None:
        params["from"] = spec.date_from.isoformat()
    if spec.date_to is not None:
        params["to"] = spec.date_to.isoformat()
    return params


async def log_in(client: httpx.AsyncClient, base_url: str, customer: str) -> str:
    login = await client.post(
        f"{base_url}/auth/login", json={"username": customer, "password": CUSTOMERS[customer]}
    )
    login.raise_for_status()
    return login.json()["token"]


def app_tools(banking: BankingClient, token: str, today: date) -> dict[str, Tool[Any]]:
    ledger = LedgerService(banking=banking)
    tools = [
        *account_tools.get_tools(service=AccountService(ledger=ledger), token=token),
        *bank_data_tools.get_tools(service=BankDataService(ledger=ledger), token=token),
        *ledger_tools.get_tools(service=ledger, token=token, today=today),
    ]
    return {tool.name: tool for tool in tools}


async def run_example(tools: dict[str, Tool[Any]], calls: list[ExampleCall]) -> list[str]:
    results = []
    for call in calls:
        tool = tools[call.tool]
        result = await tool.handler(tool.args_schema.model_validate(call.arguments))
        results.append(result.model_dump_json())
    return results


def unreachable(
    figures: list[GoldFigure], values: dict[str, Value], results: list[str]
) -> list[str]:
    """The required groups none of whose figures appear in the example's tool results."""
    found = {figure.value for result in results for figure in _figures(text=result)}
    groups: dict[str, list[GoldFigure]] = {}
    for figure in figures:
        if figure.required:
            groups.setdefault(figure.group_name, []).append(figure)
    return [
        group
        for group, members in groups.items()
        if not any(
            any(
                _found(figure=written, values=found)
                for written in _figures(text=str(values[member.name].value))
            )
            for member in members
        )
    ]


@dataclass
class Computed:
    figures: dict[str, Value]
    decoys: dict[str, Value]


async def compute_customer(
    questions: list[GoldQuestion], bank: Bank, second: SecondPath | None
) -> tuple[dict[str, Computed], list[str]]:
    """Every figure and decoy of the customer's questions, and where a second path disagrees."""
    computed: dict[str, Computed] = {}
    problems: list[str] = []
    for question in questions:
        figures = {
            figure.name: evaluate_term(term=figure, bank=bank) for figure in question.figures
        }
        decoys = {decoy.name: evaluate_term(term=decoy, bank=bank) for decoy in question.decoys}
        computed[question.id] = Computed(figures=figures, decoys=decoys)
        if second is None:
            continue
        for figure in question.figures:
            for _, spec in parts(term=figure):
                value = evaluate(spec=spec, rows=rows_of(bank=bank, source=spec.source))
                try:
                    problem = await second.check(spec=spec, value=value)
                except ValueError as error:
                    problem = str(error)
                if problem is not None:
                    problems.append(f"{question.id}/{figure.name}: {problem}")
    return computed, problems


async def compute_all(
    questions: list[GoldQuestion], check_paths: bool
) -> tuple[dict[str, Computed], list[str]]:
    """The questions' figures from the API; with check_paths also the second path and the tools."""
    settings = get_settings()
    banking = BankingClient(settings=settings)
    computed: dict[str, Computed] = {}
    problems: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=settings.banking_timeout_seconds) as client:
            info = (await client.get(f"{settings.banking_api_url}/system/info")).json()
            today = date.fromisoformat(info["today"])
            for customer, folder_name in reference.CUSTOMERS.items():
                asked = [question for question in questions if question.customer == customer]
                if not asked:
                    continue
                token = await log_in(
                    client=client, base_url=settings.banking_api_url, customer=customer
                )
                reader = BankReader(client=client, base_url=settings.banking_api_url, token=token)
                second = (
                    SecondPath(reader=reader, folder=reference.DATA_PATH / folder_name)
                    if check_paths
                    else None
                )
                found, disagree = await compute_customer(
                    questions=asked, bank=await reader.read(), second=second
                )
                computed |= found
                problems += disagree
                if not check_paths:
                    continue
                tools = app_tools(banking=banking, token=token, today=today)
                for question in asked:
                    results = await run_example(tools=tools, calls=question.example)
                    missing = unreachable(
                        figures=question.figures,
                        values=computed[question.id].figures,
                        results=results,
                    )
                    problems += [
                        f"{question.id}: no tool result of the example holds {group}"
                        for group in missing
                    ]
    finally:
        await banking.close()
    return computed, problems


def check_frozen(
    questions: list[GoldQuestion],
    computed: dict[str, Computed],
    frozen: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    problems = []
    for question in questions:
        for name, value in computed[question.id].figures.items():
            problem = freeze(frozen=frozen, question_id=question.id, name=name, value=value)
            if problem is not None:
                problems.append(problem)
    return problems


def describe(
    questions: list[GoldQuestion], computed: dict[str, Computed], show: Callable[[str], None]
) -> None:
    for question in questions:
        show(f"{question.id} [{question.split}] {question.question}")
        for name, value in computed[question.id].figures.items():
            ids = ", ".join(value.ids[:8]) + (" ..." if len(value.ids) > 8 else "")
            show(f"    {name}: {value.value} ({value.count}) {ids}")
        for name, value in computed[question.id].decoys.items():
            show(f"    decoy {name}: {value.value}")


def split_counts(questions: Iterable[GoldQuestion]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for question in questions:
        counts[question.split] = counts.get(question.split, 0) + 1
    return counts


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="freeze figures not frozen yet")
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    args = parser.parse_args()
    questions = load_gold()
    computed, problems = await compute_all(questions=questions, check_paths=True)
    frozen = load_frozen()
    problems += check_frozen(questions=questions, computed=computed, frozen=frozen)
    if not args.quiet:
        describe(questions=questions, computed=computed, show=print)  # noqa: T201
    for problem in problems:
        print(f"PROBLEM {problem}")  # noqa: T201
    print(f"{len(questions)} questions, {split_counts(questions=questions)}")  # noqa: T201
    if problems:
        return 1
    if args.write:
        FROZEN_PATH.write_text(json.dumps(frozen, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
