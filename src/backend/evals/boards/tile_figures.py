"""Live tile check: every template resolves for the four demo customers, with the design's figures.

Run against the running banking API: `uv run python -m evals.boards.tile_figures`.
"""

import asyncio
import sys
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.service import TileError, TileService

# The demo customers of the mock e-banking; the logins are public in starter/README.md.
CUSTOMERS = {
    "lukas": "lukas2026",
    "jana": "jana2026",
    "daniela": "daniela2026",
    "marco": "marco2026",
}
ERROR = {"error": True}
# (template, args, expected); a path ending in "#" is a length, ERROR expects a TileError.
Case = tuple[str, dict[str, Any], dict[str, Any] | None]
CASES: dict[str, list[Case]] = {
    "daniela": [
        (
            "payday_balance",
            {"account_id": "ACC-PRIV", "expected_from": "Patrick Rüegg"},
            {
                "figure_chf": "124.96",
                "payday": "2026-12-24",
                "day_before": "2026-12-23",
                "today_balance_chf": "3075.16",
                "days": 27,
                "per_day_chf": "4.63",
                "upcoming_count": 8,
                "alternative.amount_chf": "1050.00",
                "alternative.left_chf": "1174.96",
                "alternative.per_day_chf": "43.52",
                "source.label": "Privatkonto and 8 upcoming payments",
                "title": "Left on 23.12., the day before your salary",
            },
        ),
        (
            "bills_until_payday",
            {"account_id": "ACC-PRIV"},
            {
                "figure_chf": "2950.20",
                "rows.#": 8,
                "rows.0.payee": "Wohnbaugenossenschaft Talgut",
                "rows.0.detail": "rent for December",
                "rows.0.balance_after_chf": "1435.16",
                "rows.1.flag": "reminder",
                "rows.1.balance_after_chf": "995.16",
                "rows.2.detail": "instalment 21 of 24",
                "rows.3.detail": "mobile",
                "rows.4.payee": "Stadt Winterthur",
                "rows.4.detail": "Hort und Mittagstisch",
                "rows.5.detail": "internet",
                "rows.6.detail": "advance payment",
                "rows.7.detail": "premium for January",
                "rows.7.balance_after_chf": "124.96",
                "source.label": "8 upcoming payments",
                "title": "Bills until payday",
            },
        ),
        (
            "expected_income",
            {"counterparty": "Patrick Rüegg"},
            {
                "figure_chf": "1050.00",
                "status": "not_arrived",
                "months.#": 3,
                "months.0.month": "2026-09",
                "months.0.arrived_on": "2026-09-01",
                "months.0.state": "on_time",
                "months.1.arrived_on": "2026-10-22",
                "months.1.state": "late",
                "months.2.state": "open",
                "source.label": "2 bookings from Patrick Rüegg",
            },
        ),
        (
            "merchant_spending",
            {"merchants": ["Lidl", "Aldi", "Migros", "Denner"], "period": "this_month"},
            {
                "figure_chf": "1092.35",
                "rows.0.merchant": "Lidl",
                "rows.0.amount_chf": "505.75",
                "rows.1.merchant": "Aldi",
                "rows.1.amount_chf": "228.02",
                "rows.2.merchant": "Migros",
                "rows.2.amount_chf": "219.69",
                "rows.3.merchant": "Denner",
                "rows.3.amount_chf": "138.89",
                "source.label": "Card payments at 4 shops",
                "title": "Spending at 4 shops in November",
            },
        ),
        (
            "savings_goal",
            {"account_id": "ACC-SAV"},
            {
                "figure_chf": "284.25",
                "goal_chf": "3000",
                "percent": 9.5,
                "month_change_chf": "-600.00",
                "source.label": "2 transfers",
            },
        ),
        (
            "bill",
            {"payment_id": "PAY-0244"},
            {"figure_chf": "440.00", "due": "2026-11-30", "flag": "reminder"},
        ),
        ("savings_goal", {"account_id": "ACC-KID"}, ERROR),
        ("securities", {}, ERROR),
        ("pillar_3a", {}, ERROR),
        ("mortgage", {}, ERROR),
        ("card_bill", {"card_id": "CARD-DEBIT"}, ERROR),
        ("account_balances", {"account_ids": ["ACC-X"]}, ERROR),
        ("merchant_spending", {"merchants": ["Lidll"]}, ERROR),
        ("due_soon", {"days": 30}, None),
        ("net_worth", {}, None),
        ("monthly_spending", {"months": 6}, None),
        ("income_and_spending", {"months": 6}, None),
        ("regular_payments", {"payees": ["Lebara", "Sunrise"]}, None),
        ("account_balances", {"account_ids": ["ACC-SAV", "ACC-KID"]}, None),
    ],
    "lukas": [
        (
            "net_worth",
            {"include_pension": False},
            {
                "figure_chf": "131212.64",
                "parts.0.value_chf": "58699.68",
                "parts.1.value_chf": "72512.96",
                "source.label": "4 accounts and 1 depot, without pillar 3a",
                "title": "What you own",
            },
        ),
        (
            "due_soon",
            {"days": 30},
            {
                "figure_chf": "8302.59",
                "count": 10,
                "rows.#": 4,
                "rows.0.amount_chf": "2800.00",
                "rows.0.due": "2026-11-27",
                "rows.0.detail": "rent for December",
                "rows.1.amount_chf": "600.00",
                "rows.1.due": "2026-12-07",
                "rows.2.amount_chf": "600.00",
                "rows.2.due": "2026-12-10",
                "rows.3.amount_chf": "3301.74",
                "rows.3.payee": "Visa Gold",
                "rows.3.detail": "November",
                "rows.3.flag": "provisional",
                "source.label": "All 10 payments",
                "title": "Due in the next 30 days",
            },
        ),
        (
            "monthly_spending",
            {"months": 6},
            {
                "months.#": 6,
                "months.0.month": "2026-05",
                "months.0.total_chf": "15645.56",
                "months.1.total_chf": "9191.31",
                "months.2.total_chf": "9630.03",
                "months.3.total_chf": "7030.63",
                "months.4.total_chf": "17273.60",
                "months.5.total_chf": "10598.77",
                "highest": "2026-09",
                "title": "Where the money goes",
            },
        ),
        (
            "securities",
            {},
            {
                "figure_chf": "72512.96",
                "invested_chf": "30800.0",
                "positions": 4,
                "allocation.0.label": "Shares",
                "allocation.0.weight_pct": 93.16,
                "allocation.1.label": "Bonds",
                "allocation.1.weight_pct": 6.84,
                "source.label": "4 ETFs, CHF 30'800.00 paid in",
            },
        ),
        (
            "regular_payments",
            {"payees": ["Fitnesspark", "Swisscom", "Salt"]},
            {
                "figure_chf": "252.95",
                "rows.0.amount_chf": "119.00",
                "rows.1.amount_chf": "94.00",
                "rows.2.amount_chf": "39.95",
                "source.label": "3 payments in December",
            },
        ),
        (
            "pillar_3a",
            {},
            {
                "figure_chf": "58",
                "maximum_chf": "7258",
                "paid_chf": "6600",
                "standing_orders_chf": "600",
                "planned.#": 1,
                "planned.0.date": "2026-12-18",
                "planned.0.amount_chf": "58",
                "source.label": "1 planned transfer",
                "title": "Pillar 3a, 2026",
            },
        ),
        (
            "account_balances",
            {"account_ids": ["ACC-TAX", "ACC-RES", "ACC-LT"]},
            {"figure_chf": "48983.35", "source.label": "3 savings accounts"},
        ),
        (
            "card_bill",
            {"card_id": "CARD-VISA"},
            {
                "figure_chf": "3301.74",
                "flag": "provisional",
                "due": "2026-12-21",
                "title": "Visa Gold, November",
            },
        ),
        (
            "savings_goal",
            {"account_id": "ACC-LT"},
            {"goal_chf": "12000", "figure_chf": "37566.29"},
        ),
        ("mortgage", {}, ERROR),
        ("payday_balance", {"account_id": "ACC-PRIV"}, None),
        ("bills_until_payday", {"account_id": "ACC-PRIV"}, None),
        ("merchant_spending", {"merchants": ["Migros", "Coop"], "period": "last_month"}, None),
        ("income_and_spending", {"months": 6}, None),
        ("bill", {"payment_id": "PAY-0233"}, None),
        ("expected_income", {"counterparty": "Limmatblau"}, None),
    ],
    "jana": [
        (
            "savings_goal",
            {"account_id": "ACC-SAV"},
            {"figure_chf": "4919.20", "goal_chf": "10000"},
        ),
        ("pillar_3a", {}, None),
        ("payday_balance", {"account_id": "ACC-PRIV"}, None),
        ("bills_until_payday", {"account_id": "ACC-PRIV"}, None),
        ("due_soon", {"days": 30}, None),
        ("expected_income", {"counterparty": "Brückenwerk"}, None),
        ("merchant_spending", {"merchants": ["Migros", "Coop"], "period": "last_3_months"}, None),
        ("bill", {"payment_id": "PAY-0131"}, None),
        ("net_worth", {"include_pension": True}, None),
        ("monthly_spending", {"months": 3}, None),
        ("income_and_spending", {"months": 6}, None),
        ("securities", {}, ERROR),
        ("regular_payments", {"payees": ["Activ Fitness", "Wingo", "Sunrise"]}, None),
        ("account_balances", {"account_ids": ["ACC-PRIV", "ACC-SAV"]}, None),
        ("mortgage", {}, ERROR),
        ("card_bill", {"card_id": "CARD-DEBIT"}, ERROR),
    ],
    "marco": [
        (
            "mortgage",
            {},
            {
                "figure_chf": "862500.0",
                "annual_interest_chf": "8425.0",
                "tranches.#": 3,
                "next_maturity.loan_id": "LOAN-02",
                "next_maturity.maturity_date": "2027-03-31",
            },
        ),
        ("savings_goal", {"account_id": "ACC-HOUSE"}, {"goal_chf": "20000"}),
        ("savings_goal", {"account_id": "ACC-SAV"}, ERROR),
        ("pillar_3a", {}, None),
        ("payday_balance", {"account_id": "ACC-PRIV"}, None),
        ("bills_until_payday", {"account_id": "ACC-PRIV"}, None),
        ("due_soon", {"days": 30}, None),
        ("expected_income", {"counterparty": "Zimmerberg"}, None),
        ("merchant_spending", {"merchants": ["Migros", "Coop"]}, None),
        ("net_worth", {}, None),
        ("monthly_spending", {"months": 12}, None),
        ("income_and_spending", {"months": 3}, None),
        ("securities", {}, ERROR),
        ("account_balances", {"account_ids": ["ACC-HOUSE", "ACC-SAV"]}, None),
        ("card_bill", {"card_id": "CARD-DEBIT"}, ERROR),
    ],
}
ARGS_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("weather", {}, "Unknown template weather"),
    ("due_soon", {"days": 30, "account_id": "ACC-PRIV"}, "has no argument account_id"),
    ("bill", {}, "needs the argument payment_id"),
]


def value_at(data: Any, path: str) -> Any:
    for part in path.split("."):
        if part == "#":
            return len(data)
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def failures_of(payload: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures = []
    for path, want in expected.items():
        try:
            got = value_at(data=payload, path=path)
        except (KeyError, IndexError, TypeError):
            failures.append(f"{path}: missing")
            continue
        if isinstance(got, Decimal):
            same = got == Decimal(want)
        elif isinstance(got, date):
            same = got.isoformat() == want
        else:
            same = got == want
        if not same:
            failures.append(f"{path}: got {got!r}, want {want!r}")
    return failures


async def check_customer(tiles: TileService, username: str, token: str, today: date) -> int:
    failed = 0
    for template, args, expected in CASES[username]:
        name = f"{username} {template} {args}"
        try:
            payload = await tiles.resolve(template=template, args=args, token=token, today=today)
        except TileError as error:
            if expected is ERROR:
                print(f"ok   {name}: TileError {error}")  # noqa: T201
                continue
            failed += 1
            print(f"FAIL {name}: TileError {error}")  # noqa: T201
            continue
        if expected is ERROR:
            failed += 1
            print(f"FAIL {name}: resolved, but a TileError was expected")  # noqa: T201
            continue
        data = {**payload.model_dump(), "title": tiles.default_title(payload=payload)}
        failures = failures_of(payload=data, expected=expected or {})
        failed += bool(failures)
        status = "FAIL" if failures else "ok  "
        print(  # noqa: T201
            f"{status} {name}: {data['title']}: CHF {payload.figure_chf} ({payload.source.label},"
            f" {payload.source.count} rows)"
        )
        for failure in failures:
            print(f"       {failure}")  # noqa: T201
    return failed


def check_args(tiles: TileService) -> int:
    failed = 0
    for template, args, wanted in ARGS_CASES:
        try:
            tiles.validate_args(template=template, args=args)
            message = "no error"
        except TileError as error:
            message = str(error)
        ok = wanted in message
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} args {template} {args}: {message}")  # noqa: T201
    return failed


async def main() -> int:
    settings = get_settings()
    banking = BankingClient(settings=settings)
    failed = 0
    try:
        today = await LedgerService(banking=banking).get_today()
        print(f"Banking API: {settings.banking_api_url}, today {today}")  # noqa: T201
        async with httpx.AsyncClient(timeout=settings.banking_timeout_seconds) as bank:
            for username, password in CUSTOMERS.items():
                login = await bank.post(
                    f"{settings.banking_api_url}/auth/login",
                    json={"username": username, "password": password},
                )
                login.raise_for_status()
                ledger = LedgerService(banking=banking)
                tiles = TileService(
                    banking=banking, ledger=ledger, recurring=RecurringPaymentService(ledger=ledger)
                )
                failed += await check_customer(
                    tiles=tiles, username=username, token=login.json()["token"], today=today
                )
        ledger = LedgerService(banking=banking)
        failed += check_args(
            tiles=TileService(
                banking=banking, ledger=ledger, recurring=RecurringPaymentService(ledger=ledger)
            )
        )
    finally:
        await banking.close()
    print(f"{failed} failed")  # noqa: T201
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
