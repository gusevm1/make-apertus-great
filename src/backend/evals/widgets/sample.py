"""Lukas's DATA as the benchmark builds it, flattened into one object for the catalogue gallery."""

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

import httpx

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.schemas import ForecastMonthsArgs, LedgerRow, MonthTrend
from app.features.ledger.service import LedgerService
from evals.widgets.data import build_all

# A demo customer of the mock e-banking; the logins are public in starter/README.md.
LOGIN = {"username": "lukas", "password": "lukas2026"}
LOGIN_TIMEOUT_SECONDS = 30
# The bank writes a savings goal as text, such as "Japanreise 2027: CHF 12'000".
GOAL = re.compile(r"^(?P<name>.+?):\s*CHF\s*(?P<amount>[\d']+(?:\.\d+)?)$")
# The rent scenario of the gallery: today's rent and two higher ones.
RENT_CASES = [("Rent today", 0), ("200 more", 200), ("400 more", 400)]
# Made-up budgets for the gallery, as a share of what was spent: the second one is overspent.
BUDGET_SHARES = [1.15, 0.85, 1.1, 1.2]
# Spending groups named in the waterfall before the rest becomes one step.
FLOW_GROUPS = 3


async def lukas_data() -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=LOGIN_TIMEOUT_SECONDS) as bank:
        login = await bank.post(f"{settings.banking_api_url}/auth/login", json=LOGIN)
    login.raise_for_status()
    banking = BankingClient(settings=settings)
    ledger = LedgerService(banking=banking)
    token = login.json()["token"]
    try:
        tasks = await build_all(ledger=ledger, token=token)
        accounts = await ledger.read(path="/accounts", token=token)
        trend = await ledger.forecast_months(
            token=token, args=ForecastMonthsArgs(), today=await ledger.get_today()
        )
        ledger_rows = await ledger.list_rows(token=token)
    finally:
        await banking.close()
    months = tasks["monthly_spending"]["months"]
    payments = tasks["upcoming_payments"]["payments"]
    steps = flow(rows=ledger_rows, month=months[-1]["label"])
    return {
        "months": months,
        "months_total_chf": tasks["monthly_spending"]["total_chf"],
        # The last month against the one before, computed here on the server for the gallery.
        "months_change_chf": round(months[-1]["total_chf"] - months[-2]["total_chf"], 2),
        "payments": tasks["upcoming_payments"]["payments"],
        "payments_total_chf": tasks["upcoming_payments"]["total_chf"],
        "payees": tasks["where_money_goes"]["payees"],
        "payees_total_chf": tasks["where_money_goes"]["total_chf"],
        "years": tasks["year_vs_year"]["months"],
        "accounts": tasks["liquidity"]["accounts"],
        "liquidity_total_chf": tasks["liquidity"]["total_liquidity_chf"],
        "goals": goals(accounts=accounts["items"]),
        "forecast": forecast(trend=trend),
        "rent_cases": rent_cases(trend=trend, payments=payments),
        "days": days(rows=ledger_rows, months=[month["label"] for month in months[-3:]]),
        "budgets": sample_budgets(payees=tasks["where_money_goes"]["payees"]),
        "flow": steps,
        "flow_left_chf": steps[-1]["end_chf"] if len(steps) > 0 else 0.0,
    }


def days(rows: list[LedgerRow], months: list[str]) -> list[dict[str, Any]]:
    # Spending per day; a spending row is money out, so its total is positive.
    by_day: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in rows:
        if row.kind == "spending" and row.date.strftime("%Y-%m") in months:
            by_day[row.date.isoformat()].append(row)
    found = []
    for day, spent in sorted(by_day.items()):
        total = -sum((row.amount_chf for row in spent), Decimal(0))
        if total > 0:
            found.append(
                {"date": day, "total_chf": float(total), "booking_ids": [row.id for row in spent]}
            )
    return found


def sample_budgets(payees: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # The bank holds no budgets: these are made up for the gallery, one of them overspent.
    return [
        {
            "payee": payee["label"],
            "spent_chf": payee["total_chf"],
            "budget_chf": round(payee["total_chf"] * share / 50) * 50,
            "booking_ids": payee["booking_ids"],
        }
        for payee, share in zip(
            (payee for payee in payees if payee["label"] != "Other"),
            BUDGET_SHARES,
            strict=False,
        )
    ]


def flow(rows: list[LedgerRow], month: str) -> list[dict[str, Any]]:
    # From the month's income through its largest spending groups to what is left.
    in_month = [row for row in rows if row.date.strftime("%Y-%m") == month]
    income = sum((row.amount_chf for row in in_month if row.kind == "credit"), Decimal(0))
    groups: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in in_month:
        if row.kind == "spending":
            groups[row.counterparty if row.counterparty is not None else row.text].append(row)
    ranked = sorted(groups.items(), key=lambda item: sum(r.amount_chf for r in item[1]))
    named = ranked[:FLOW_GROUPS]
    rest = [row for _, group in ranked[FLOW_GROUPS:] for row in group]
    steps: list[tuple[str, list[LedgerRow]]] = list(named)
    if len(rest) > 0:
        steps.append(("Other spending", rest))
    found = [
        {
            "step": "Income",
            "start_chf": 0.0,
            "end_chf": float(income),
            "amount_chf": float(income),
            "booking_ids": [row.id for row in in_month if row.kind == "credit"],
        }
    ]
    level = income
    for name, group in steps:
        amount = sum((row.amount_chf for row in group), Decimal(0))
        found.append(
            {
                "step": name,
                "start_chf": float(level),
                "end_chf": float(level + amount),
                "amount_chf": float(amount),
                "booking_ids": [row.id for row in group],
            }
        )
        level += amount
    return found


def forecast(trend: MonthTrend) -> list[dict[str, Any]]:
    actual = [
        {
            "month": month.month,
            "net_chf": float(month.money_out_chf + month.money_in_chf),
            "kind": "actual",
            "low_chf": None,
            "high_chf": None,
            "booking_ids": trend.row_ids[month.month],
        }
        for month in trend.months
    ]
    ahead = [
        {
            "month": month.month,
            "net_chf": float(month.trend_chf),
            "kind": "forecast",
            # The range runs between the trend and the average of the months behind it.
            "low_chf": float(min(month.trend_chf, month.average_chf)),
            "high_chf": float(max(month.trend_chf, month.average_chf)),
        }
        for month in trend.projection
    ]
    return actual + ahead


def rent_cases(trend: MonthTrend, payments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # What is left over per month on average, less what a higher rent would cost.
    rent = next(
        (item["amount_chf"] for item in payments if item["description"].startswith("Miete")), None
    )
    if rent is None:
        return []
    return [
        {
            "case": name,
            "rent_chf": rent + extra,
            "left_chf": float(trend.average_chf) - extra,
        }
        for name, extra in RENT_CASES
    ]


def goals(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for account in accounts:
        text = account.get("savings_goal")
        match = None if text is None else GOAL.match(text)
        if match is None:
            continue
        found.append(
            {
                "name": match.group("name"),
                "account": account["name"],
                "saved_chf": account["current_balance_chf"],
                "goal_chf": float(match.group("amount").replace("'", "")),
            }
        )
    return found
