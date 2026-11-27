"""Lukas's DATA as the benchmark builds it, flattened into one object for the catalogue gallery."""

import re
from typing import Any

import httpx

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.schemas import ForecastMonthsArgs, MonthTrend
from app.features.ledger.service import LedgerService
from evals.widgets.data import build_all

# A demo customer of the mock e-banking; the logins are public in starter/README.md.
LOGIN = {"username": "lukas", "password": "lukas2026"}
LOGIN_TIMEOUT_SECONDS = 30
# The bank writes a savings goal as text, such as "Japanreise 2027: CHF 12'000".
GOAL = re.compile(r"^(?P<name>.+?):\s*CHF\s*(?P<amount>[\d']+(?:\.\d+)?)$")
# The rent scenario of the gallery: today's rent and two higher ones.
RENT_CASES = [("Rent today", 0), ("200 more", 200), ("400 more", 400)]


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
    finally:
        await banking.close()
    months = tasks["monthly_spending"]["months"]
    payments = tasks["upcoming_payments"]["payments"]
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
    }


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
