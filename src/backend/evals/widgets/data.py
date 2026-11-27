"""The DATA of each benchmark task, computed on the server from one persona's bank data."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.features.ledger.schemas import LedgerRow
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService

TOP_PAYEES = 8


async def build_all(ledger: LedgerService, token: str) -> dict[str, dict[str, Any]]:
    today = await ledger.get_today()
    rows = await ledger.list_rows(token=token)
    spending = [row for row in rows if row.kind == "spending"]
    recurring = await RecurringPaymentService(ledger=ledger).list_recurring(
        token=token, today=today
    )
    upcoming = await ledger.read(
        path="/upcoming-payments",
        token=token,
        params={"from": today.isoformat(), "to": (today + timedelta(days=30)).isoformat()},
    )
    accounts = await ledger.read(path="/accounts", token=token)
    return {
        "monthly_spending": monthly_spending(
            rows=spending, months=last_full_months(today=today, count=6)
        ),
        "upcoming_payments": {
            "from": today.isoformat(),
            "to": (today + timedelta(days=30)).isoformat(),
            "total_chf": upcoming["total_chf"],
            "payments": [
                {
                    "due_date": item["due_date"],
                    "payee": item["payee_name"],
                    "description": item["description"],
                    "amount_chf": item["amount_chf"],
                }
                for item in upcoming["items"]
            ],
        },
        "pricier_subscriptions": {
            "subscriptions": [
                payment.model_dump(mode="json")
                for payment in recurring.recurring
                if payment.price_changes
            ]
        },
        "year_vs_year": year_vs_year(rows=spending, today=today),
        "liquidity": {
            "total_liquidity_chf": accounts["total_liquidity_chf"],
            "as_of": accounts["as_of"],
            "accounts": [
                {
                    "name": item["name"],
                    "type": item["type"],
                    "balance_chf": item["current_balance_chf"],
                }
                for item in accounts["items"]
                if item["type"] != "pillar3a"
            ],
        },
        "where_money_goes": by_payee(rows=spending, months=last_full_months(today=today, count=3)),
    }


def last_full_months(today: date, count: int) -> list[str]:
    first_of_month = today.replace(day=1)
    months = []
    for _ in range(count):
        first_of_month = (first_of_month - timedelta(days=1)).replace(day=1)
        months.append(first_of_month.strftime("%Y-%m"))
    return months[::-1]


def monthly_spending(rows: list[LedgerRow], months: list[str]) -> dict[str, Any]:
    by_month = _group(rows=rows, key=lambda row: row.date.strftime("%Y-%m"))
    points = [_point(label=month, rows=by_month.get(month, [])) for month in months]
    return {"unit": "CHF", "months": points, "total_chf": _total(rows=_flatten(by_month, months))}


def year_vs_year(rows: list[LedgerRow], today: date) -> dict[str, Any]:
    last_month = today.replace(day=1) - timedelta(days=1)
    points = []
    for year in (today.year - 1, today.year):
        by_month = _group(
            rows=[row for row in rows if row.date.year == year], key=lambda row: row.date.month
        )
        points += [
            {
                "month": f"{month:02d}",
                "year": str(year),
                **_point(label=f"{year}-{month:02d}", rows=by_month.get(month, [])),
            }
            for month in range(1, last_month.month + 1)
        ]
    return {"unit": "CHF", "months": points}


def by_payee(rows: list[LedgerRow], months: list[str]) -> dict[str, Any]:
    in_period = [row for row in rows if row.date.strftime("%Y-%m") in months]
    groups = _group(
        rows=in_period,
        key=lambda row: row.text if row.counterparty is None else row.counterparty,
    )
    ranked = sorted(groups.items(), key=lambda item: _total(rows=item[1]), reverse=True)
    points = [_point(label=payee, rows=group) for payee, group in ranked[:TOP_PAYEES]]
    rest = [row for _, group in ranked[TOP_PAYEES:] for row in group]
    if rest:
        points.append(_point(label="Other", rows=rest))
    return {
        "unit": "CHF",
        "from_month": months[0],
        "to_month": months[-1],
        "payees": points,
        "total_chf": _total(rows=in_period),
    }


def _group(rows: Iterable[LedgerRow], key: Any) -> dict[Any, list[LedgerRow]]:
    groups: dict[Any, list[LedgerRow]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return groups


def _flatten(groups: dict[Any, list[LedgerRow]], keys: list[Any]) -> list[LedgerRow]:
    return [row for key in keys for row in groups.get(key, [])]


def _point(label: str, rows: list[LedgerRow]) -> dict[str, Any]:
    return {"label": label, "total_chf": _total(rows=rows), "booking_ids": [row.id for row in rows]}


def _total(rows: list[LedgerRow]) -> float:
    # Spending is negative in the ledger; a chart shows it as a positive amount.
    return float(-sum((row.amount_chf for row in rows), Decimal(0)))
