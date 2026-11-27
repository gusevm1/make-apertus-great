"""Live ledger check: the ledger of each demo customer adds up to the banking API's own totals."""

import asyncio
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService

# The demo customers of the mock e-banking; the logins are public in starter/README.md.
CUSTOMERS = {
    "lukas": "lukas2026",
    "jana": "jana2026",
    "daniela": "daniela2026",
    "marco": "marco2026",
}
LOAN_TYPES = {"loan_interest", "loan_amortisation"}
CENT = Decimal("0.01")


def chf(amount: float | Decimal) -> Decimal:
    return Decimal(str(amount)).quantize(CENT)


def account_failures(rows: list[LedgerRow], accounts: list[dict[str, Any]]) -> list[str]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        if row.source == "booking":
            totals[row.account_id] += row.amount_chf
    failures = []
    for account in accounts:
        computed = chf(
            amount=chf(amount=account["opening_balance"]) + totals[account["account_id"]]
        )
        if computed != chf(amount=account["current_balance"]):
            failures.append(
                f"account {account['account_id']}: opening balance plus bookings is {computed},"
                f" the bank says {chf(amount=account['current_balance'])}"
            )
    return failures


def statement_failures(
    rows: list[LedgerRow], statements: list[dict[str, Any]], data_from: date
) -> tuple[list[str], list[str]]:
    """Failures, and the statements skipped because their purchases predate the data."""
    by_id = {row.id: row for row in rows}
    failures: list[str] = []
    skipped: list[str] = []
    for statement in statements:
        statement_id = statement["statement_id"]
        total = chf(amount=statement["total_chf"])
        if date.fromisoformat(statement["period_to"]) < data_from:
            skipped.append(statement_id)
        else:
            purchases = [
                row
                for row in rows
                if row.source == "card_transaction"
                and row.card_id == statement["card_id"]
                and row.statement_id == statement_id
            ]
            purchased = chf(amount=-sum((row.amount_chf for row in purchases), Decimal()))
            if purchased != total:
                failures.append(
                    f"statement {statement_id}: {len(purchases)} purchases add up to {purchased},"
                    f" the statement total is {total}"
                )
        booking_id = statement["booking_id"]
        if booking_id is None:
            continue
        settlement = by_id.get(booking_id)
        if settlement is None:
            failures.append(
                f"statement {statement_id}: settlement {booking_id} is not in the ledger"
            )
            continue
        if chf(amount=-settlement.amount_chf) != total or settlement.statement_id != statement_id:
            failures.append(
                f"statement {statement_id}: settlement {booking_id} is {-settlement.amount_chf}"
                f" for {settlement.statement_id}, the statement total is {total}"
            )
    known = {statement["statement_id"] for statement in statements}
    failures += [
        f"settlement {row.id}: names statement {row.statement_id}, which the card does not list"
        for row in rows
        if row.kind == "card_settlement" and row.statement_id not in known
    ]
    return failures, skipped


def loan_failures(rows: list[LedgerRow], charges: list[dict[str, Any]]) -> list[str]:
    by_id = {row.id: row for row in rows}
    failures = []
    for charge in charges:
        booking = by_id.get(charge["booking_id"])
        if booking is None:
            failures.append(
                f"loan charge {charge['loan_tx_id']}: booking {charge['booking_id']}"
                " is not in the ledger"
            )
            continue
        is_same = (
            chf(amount=-booking.amount_chf) == chf(amount=charge["amount"])
            and booking.loan_id == charge["loan_id"]
            and booking.loan_charge == charge["type"]
        )
        if not is_same:
            failures.append(
                f"loan charge {charge['loan_tx_id']}: {charge['amount']} {charge['type']} on"
                f" {charge['loan_id']}, booking {booking.id} is {booking.amount_chf}"
                f" {booking.loan_charge} on {booking.loan_id}"
            )
    failures += [
        f"booking {row.id}: a {row.transaction_type} without its loan"
        for row in rows
        if row.transaction_type in LOAN_TYPES and row.loan_id is None
    ]
    return failures


def total_failures(
    rows: list[LedgerRow], booking_sum: Decimal, bill_sum: Decimal, purchase_sum: Decimal
) -> list[str]:
    """`purchase_sum` is the cards' own sum, positive for a charge as the card lists it."""
    expected = chf(amount=booking_sum - bill_sum - purchase_sum)
    ledger_sum = chf(
        amount=sum((row.amount_chf for row in rows if row.kind != "card_settlement"), Decimal())
    )
    if ledger_sum == expected:
        return []
    return [
        f"totals: spending, credits and own transfers add up to {ledger_sum}, the bank's bookings"
        f" with card purchases in place of the bills to {expected}"
    ]


async def bank_sum(ledger: LedgerService, path: str, token: str, params: dict[str, Any]) -> Any:
    return await ledger.read(path=path, token=token, params={"limit": 1} | params)


async def check_customer(ledger: LedgerService, token: str) -> tuple[list[str], list[str], str]:
    """The customer's failed checks, the statements skipped, and what was checked."""
    rows = await ledger.list_rows(token=token)
    info = await ledger.banking.get(path="/system/info")
    accounts = await ledger.read(path="/accounts", token=token)
    charges = await ledger.read(path="/loan-transactions", token=token)
    bookings = await bank_sum(ledger=ledger, path="/bookings", token=token, params={})
    bills = await bank_sum(
        ledger=ledger,
        path="/bookings",
        token=token,
        params={"transaction_type": "card_settlement"},
    )
    cards = await ledger.read(path="/cards", token=token)
    statements: list[dict[str, Any]] = []
    purchase_sum = Decimal()
    for card in cards["items"]:
        if card["type"] != "credit":
            continue
        card_path = f"/cards/{quote(card['card_id'], safe='')}"
        statements += (await ledger.read(path=f"{card_path}/statements", token=token))["items"]
        purchases = await bank_sum(
            ledger=ledger, path=f"{card_path}/transactions", token=token, params={}
        )
        purchase_sum += chf(amount=purchases["sum_chf"])

    failures = account_failures(rows=rows, accounts=accounts["items"])
    card_failures, skipped = statement_failures(
        rows=rows, statements=statements, data_from=date.fromisoformat(info["data_from"])
    )
    failures += card_failures
    failures += loan_failures(rows=rows, charges=charges["items"])
    failures += total_failures(
        rows=rows,
        booking_sum=chf(amount=bookings["sum_credit"]) + chf(amount=bookings["sum_debit"]),
        bill_sum=chf(amount=bills["sum_credit"]) + chf(amount=bills["sum_debit"]),
        purchase_sum=purchase_sum,
    )
    checked = (
        f"{len(rows)} rows, {len(accounts['items'])} accounts, {len(statements)} statements,"
        f" {len(charges['items'])} loan charges"
    )
    return failures, skipped, checked


async def main() -> int:
    settings = get_settings()
    ledger = LedgerService(banking=BankingClient(settings=settings))
    failed = 0
    try:
        print(f"Banking API: {settings.banking_api_url}")  # noqa: T201
        async with httpx.AsyncClient(timeout=settings.banking_timeout_seconds) as bank:
            for username, password in CUSTOMERS.items():
                login = await bank.post(
                    f"{settings.banking_api_url}/auth/login",
                    json={"username": username, "password": password},
                )
                if login.status_code != 200:
                    print(f"FAIL {username}: login {login.status_code} {login.text[:200]}")  # noqa: T201
                    failed += 1
                    continue
                failures, skipped, checked = await check_customer(
                    ledger=ledger, token=login.json()["token"]
                )
                print(f"{'FAIL' if failures else 'ok  '} {username}: {checked}")  # noqa: T201
                for failure in failures:
                    print(f"     {failure}")  # noqa: T201
                if skipped:
                    print(f"     skipped, purchases before the data: {', '.join(skipped)}")  # noqa: T201
                failed += bool(failures)
    finally:
        await ledger.banking.close()
    print(f"{len(CUSTOMERS) - failed} of {len(CUSTOMERS)} customers add up")  # noqa: T201
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
