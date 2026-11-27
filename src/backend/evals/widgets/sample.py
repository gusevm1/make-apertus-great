"""Lukas's DATA as the benchmark builds it, flattened into one object for the catalogue gallery."""

import re
from typing import Any

import httpx

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from evals.widgets.data import build_all

# A demo customer of the mock e-banking; the logins are public in starter/README.md.
LOGIN = {"username": "lukas", "password": "lukas2026"}
LOGIN_TIMEOUT_SECONDS = 30
# The bank writes a savings goal as text, such as "Japanreise 2027: CHF 12'000".
GOAL = re.compile(r"^(?P<name>.+?):\s*CHF\s*(?P<amount>[\d']+(?:\.\d+)?)$")


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
    finally:
        await banking.close()
    return {
        "months": tasks["monthly_spending"]["months"],
        "months_total_chf": tasks["monthly_spending"]["total_chf"],
        "payments": tasks["upcoming_payments"]["payments"],
        "payments_total_chf": tasks["upcoming_payments"]["total_chf"],
        "payees": tasks["where_money_goes"]["payees"],
        "payees_total_chf": tasks["where_money_goes"]["total_chf"],
        "years": tasks["year_vs_year"]["months"],
        "accounts": tasks["liquidity"]["accounts"],
        "liquidity_total_chf": tasks["liquidity"]["total_liquidity_chf"],
        "goals": goals(accounts=accounts["items"]),
    }


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
