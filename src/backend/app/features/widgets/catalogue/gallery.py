"""Every catalogue component on Lukas's data, live at 360 and 1000 px and static at 440 px."""

import asyncio
import html
from pathlib import Path
from typing import Any

import httpx

from app.clients.banking import BankingClient
from app.core.config import get_settings
from app.features.ledger.service import LedgerService
from app.features.widgets.catalogue.render import render
from app.features.widgets.catalogue.schemas import WidgetSpec
from app.features.widgets.catalogue.values import display

OUT = Path(__file__).resolve().parents[4] / "evals" / "widgets" / "results" / "catalogue"
# A demo customer of the mock e-banking; the logins are public in starter/README.md.
LOGIN = {"username": "lukas", "password": "lukas2026"}
LOGIN_TIMEOUT_SECONDS = 30
FRAMES = [("live", 360), ("live", 1000), ("static", 440)]


def specs(data: dict[str, Any]) -> dict[str, WidgetSpec]:
    last, before = data["months"][-1]["label"], data["months"][-2]["label"]
    last_name, before_name = (
        display(field="label", value=last),
        display(field="label", value=before),
    )
    raw: dict[str, dict[str, Any]] = {
        "kpi": {
            "title": "Spending",
            "body": {
                "type": "kpi",
                "label": f"Spending {last_name}",
                "value": "months[5].total_chf",
                "compare": "months[4].total_chf",
                "compare_label": before_name,
            },
        },
        "stat_row": {
            "title": "Largest payees",
            "subtitle": "Last 3 months",
            "body": {
                "type": "stat_row",
                "stats": [
                    {"label": data["payees"][i]["label"], "value": f"payees[{i}].total_chf"}
                    for i in range(3)
                ],
            },
        },
        "table": {
            "title": "Due in the next 30 days",
            "body": {
                "type": "table",
                "rows": "payments",
                "columns": ["due_date", "payee", "amount_chf"],
                "total": "payments_total_chf",
            },
        },
        "list": {
            "title": "Your accounts",
            "body": {
                "type": "list",
                "rows": "accounts",
                "label": "name",
                "detail": "type",
                "value": "balance_chf",
            },
        },
        "bar_chart": {
            "title": "Monthly spending",
            "subtitle": "Last 6 months",
            "body": {
                "type": "bar_chart",
                "data": "months",
                "x": "label",
                "y": "total_chf",
                "highlight": last,
            },
        },
        "bar_chart_horizontal": {
            "title": "Where the money goes",
            "subtitle": "Last 3 months",
            "body": {
                "type": "bar_chart",
                "data": "payees",
                "x": "label",
                "y": "total_chf",
                "horizontal": True,
            },
        },
        "line_chart": {
            "title": "This year against last year",
            "body": {
                "type": "line_chart",
                "data": "years",
                "x": "month",
                "y": "total_chf",
                "series": "year",
            },
        },
        "grid_stack": {
            "title": "Overview",
            "body": {
                "type": "stack",
                "children": [
                    {
                        "type": "grid",
                        "columns": 2,
                        "children": [
                            {"type": "kpi", "label": "Liquidity", "value": "liquidity_total_chf"},
                            {
                                "type": "kpi",
                                "label": "Spent in 3 months",
                                "value": "payees_total_chf",
                            },
                        ],
                    },
                    {"type": "line_chart", "data": "months", "x": "label", "y": "total_chf"},
                ],
            },
        },
    }
    return {name: WidgetSpec.model_validate(spec) for name, spec in raw.items()}


async def sample_data() -> dict[str, Any]:
    """Lukas's DATA as the benchmark of #23 builds it, flattened into one object."""
    from evals.widgets.data import build_all

    settings = get_settings()
    async with httpx.AsyncClient(timeout=LOGIN_TIMEOUT_SECONDS) as bank:
        login = await bank.post(f"{settings.banking_api_url}/auth/login", json=LOGIN)
    login.raise_for_status()
    banking = BankingClient(settings=settings)
    try:
        tasks = await build_all(ledger=LedgerService(banking=banking), token=login.json()["token"])
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
    }


def write_gallery(data: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    sections = []
    for name, spec in specs(data=data).items():
        for form in ("live", "static"):
            (OUT / f"{name}-{form}.html").write_text(
                render(spec=spec, data=data, form=form), encoding="utf-8"
            )
        frames = "".join(
            f"<figure><figcaption>{form}, {width} px</figcaption>"
            f'<iframe src="{html.escape(name)}-{form}.html" sandbox="allow-scripts" '
            f'style="width:{width}px"></iframe></figure>'
            for form, width in FRAMES
        )
        sections.append(
            f'<section><h2>{html.escape(name)}</h2><div class="frames">{frames}</div></section>'
        )
    page = (
        '<!doctype html><meta charset="utf-8"><title>Widget catalogue</title><style>'
        "body{font:14px system-ui;margin:24px;background:#f2f3f3;color:#12202a}"
        ".frames{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}"
        "iframe{height:560px;border:0;border-radius:12px;background:#fff}"
        "figure{margin:0}figcaption{font-size:12px;color:#5b6870;margin-bottom:4px}"
        f"</style><h1>Widget catalogue</h1>{''.join(sections)}"
    )
    index = OUT / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


if __name__ == "__main__":
    print(write_gallery(data=asyncio.run(sample_data())))  # noqa: T201
