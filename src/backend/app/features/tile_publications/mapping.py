"""A tile's payload as a `declarative` dashboard widget (starter/docs/custom-widgets.md §3, §5)."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.features.boards.schemas import Tile
from app.features.tile_publications.schemas import TileSnapshot
from app.features.tiles.schemas import (
    AccountBalancesPayload,
    AnyPayload,
    BillPayload,
    BillRow,
    BillsUntilPaydayPayload,
    CardBillPayload,
    DueSoonPayload,
    ExpectedIncomePayload,
    IncomeAndSpendingPayload,
    MerchantSpendingPayload,
    MonthlySpendingPayload,
    MortgagePayload,
    NetWorthPayload,
    PaydayBalancePayload,
    Pillar3aPayload,
    RegularPaymentsPayload,
    SavingsGoalPayload,
    SecuritiesPayload,
    Source,
)

TABLE_ROWS_MAX = 8
GRID_COLUMNS = 3
# From three columns on, a one-wide card cuts the amount column off.
WIDE_TABLE_COLUMNS = 3
MONTHS = "January February March April May June July August September October November December"
MONTH_NAMES = MONTHS.split()


def tile_marker(tile_id: UUID) -> str:
    """The `custom.prompt` that finds this tile's widget on a dashboard again."""
    return f"trustroom-tile:{tile_id}"


def widget_of(payload: AnyPayload, title: str, tile_id: UUID, today: date) -> dict[str, Any]:
    """The `title` and `custom` of the tile's widget: a snapshot of the figures as of `today`."""
    spec = _spec(payload=payload)
    spec["subtitle"] = f"As of {_day(day=today)}"
    custom: dict[str, Any] = {
        "format": "declarative",
        "spec": spec,
        "prompt": tile_marker(tile_id=tile_id),
        "created_by": "TrustRoom",
    }
    booking_ids = _booking_ids(source=payload.source)
    if booking_ids:
        custom["source"] = {"booking_ids": booking_ids}
        # A tile names only its first bookings, so the widget says when the link shows a part.
        if len(booking_ids) < payload.source.count:
            note = (
                f"The link opens only {len(booking_ids)} of the {payload.source.count} payments "
                "behind this tile."
            )
            spec["footnote"] = f"{spec['footnote']} {note}" if "footnote" in spec else note
    return {"title": title, "custom": custom}


def snapshot_widget_of(
    widget: dict[str, Any], snapshot: TileSnapshot, tile: Tile, today: date
) -> dict[str, Any]:
    """The widget with the page's own drawing of the tile in place of the e-banking's."""
    custom = {key: value for key, value in widget["custom"].items() if key != "spec"}
    custom |= {
        "format": "html",
        # Our e-banking reads the board and the tile from this comment and frames the live tile.
        "html": f"<!-- trustroom-tile:{tile.board_id}/{tile.id} -->{snapshot.html}",
        "height": snapshot.height,
        "prompt": f"A tile from your TrustRoom, with the figures of {_day(day=today)}",
    }
    return {"title": widget["title"], "custom": custom}


def is_widget_of(widget: dict[str, Any], tile_id: UUID) -> bool:
    """Whether the dashboard widget is this tile's copy, in either format."""
    custom = widget.get("custom") or {}
    in_page = f"/{tile_id} -->" in (custom.get("html") or "")[:120]
    return custom.get("prompt") == tile_marker(tile_id=tile_id) or in_page


def widget_width(widget: dict[str, Any]) -> int:
    """The grid columns the widget needs so that every amount shows in full."""
    spec = widget["custom"]["spec"]
    return 2 if spec["type"] == "table" and len(spec["columns"]) >= WIDE_TABLE_COLUMNS else 1


def first_free_position(widgets: list[dict[str, Any]], width: int) -> dict[str, int]:
    """The first one-row slot of `width` columns, row by row, that no widget covers."""
    taken = {
        (box["col"] + col, box["row"] + row)
        for box in (widget["position"] for widget in widgets)
        for col in range(box.get("width", 1))
        for row in range(box.get("height", 1))
    }
    row = 0
    while True:
        for col in range(GRID_COLUMNS - width + 1):
            if all((col + step, row) not in taken for step in range(width)):
                return {"col": col, "row": row, "width": width, "height": 1}
        row += 1


def _spec(payload: AnyPayload) -> dict[str, Any]:
    match payload:
        case BillsUntilPaydayPayload():
            return _bills_table(
                rows=payload.rows, count=len(payload.rows), total=payload.figure_chf
            )
        case DueSoonPayload():
            return _bills_table(rows=payload.rows, count=payload.count, total=payload.figure_chf)
        case RegularPaymentsPayload():
            return _table(
                columns=[
                    _column(key="payee", label="Payee"),
                    _column(key="next_due", label="Next due", kind="date"),
                    _column(key="amount", label="Amount", kind="currency"),
                ],
                rows=[
                    {
                        "payee": row.payee,
                        "next_due": row.next_due.isoformat(),
                        "amount": float(row.amount_chf),
                    }
                    for row in payload.rows
                ],
                count=len(payload.rows),
                footer={"payee": "Total", "amount": float(payload.figure_chf)},
                noun="payments",
            )
        case AccountBalancesPayload():
            return _table(
                columns=[
                    _column(key="name", label="Account"),
                    _column(key="balance", label="Balance", kind="currency"),
                ],
                rows=[
                    {"name": row.name, "balance": float(row.balance_chf)} for row in payload.rows
                ],
                count=len(payload.rows),
                footer={"name": "Total", "balance": float(payload.figure_chf)},
                noun="accounts",
            )
        case MerchantSpendingPayload():
            spec = _table(
                columns=[
                    _column(key="merchant", label="Merchant"),
                    _column(key="count", label="Payments", kind="number"),
                    _column(key="amount", label="Amount", kind="currency"),
                ],
                rows=[
                    {"merchant": row.merchant, "count": row.count, "amount": float(row.amount_chf)}
                    for row in payload.rows
                ],
                count=len(payload.rows),
                footer={"merchant": "Total", "amount": float(payload.figure_chf)},
                noun="merchants",
            )
            period = f"From {_day(day=payload.date_from)} to {_day(day=payload.date_to)}"
            return {**spec, "footnote": _sentence(text=period)}
        case MortgagePayload():
            return _table(
                columns=[
                    _column(key="product", label="Tranche"),
                    _column(key="rate", label="Rate", kind="percent"),
                    _column(key="matures", label="Runs out", kind="date"),
                    _column(key="balance", label="Balance", kind="currency"),
                ],
                rows=[
                    {
                        "product": tranche.product,
                        "rate": tranche.interest_rate,
                        "balance": float(tranche.balance_chf),
                        **(
                            {}
                            if tranche.maturity_date is None
                            else {"matures": tranche.maturity_date.isoformat()}
                        ),
                    }
                    for tranche in payload.tranches
                ],
                count=len(payload.tranches),
                footer={"product": "Total", "balance": float(payload.figure_chf)},
                noun="tranches",
            )
        case MonthlySpendingPayload():
            return _bar(
                title="Spending",
                data=[
                    {"label": month.month, "value": float(month.total_chf)}
                    for month in payload.months
                ],
                footnote=f"On average {_chf(amount=payload.figure_chf)} per month.",
            )
        case IncomeAndSpendingPayload():
            return _bar(
                title="Income and spending",
                data=[
                    {"label": month.month, "series": series, "value": float(value)}
                    for month in payload.months
                    for series, value in (
                        ("Income", month.income_chf),
                        ("Spending", month.spending_chf),
                    )
                ],
                footnote=f"On average {_chf(amount=payload.figure_chf)} left per month.",
            )
        case _:
            return _kpi(payload=payload)


def _kpi(payload: AnyPayload) -> dict[str, Any]:
    # The footnote says what the one figure is; a title such as "Pillar 3a" does not.
    spec: dict[str, Any] = {"type": "kpi", "value": float(payload.figure_chf), "currency": "CHF"}
    note = payload.source.label
    match payload:
        case PaydayBalancePayload():
            note = (
                f"Left on {_day(day=payload.day_before)}, the day before the salary on "
                f"{_day(day=payload.payday)}"
            )
        case ExpectedIncomePayload():
            arrived = "arrived" if payload.status == "arrived" else "not arrived yet"
            note = f"From {payload.counterparty}, {arrived} this month"
        case SavingsGoalPayload():
            spec["delta"] = float(payload.month_change_chf)
            spec["delta_label"] = f"in {MONTH_NAMES[int(payload.month[5:7]) - 1]}"
            note = f"{payload.percent:.1f}% of the goal of {_chf(amount=payload.goal_chf)}"
        case BillPayload():
            note = f"To {payload.payee}, due {_day(day=payload.due)}"
        case NetWorthPayload():
            note = f"{'With' if payload.includes_pension else 'Without'} pillar 3a"
        case SecuritiesPayload():
            note = f"Value of the depot, {_chf(amount=payload.invested_chf)} invested"
        case Pillar3aPayload():
            maximum = f"the {payload.year} maximum of {_chf(amount=payload.maximum_chf)}"
            note = (
                f"Missing to {maximum} after the standing orders"
                if payload.figure_chf >= 0
                else f"Negative: the standing orders go over {maximum}"
            )
        case CardBillPayload():
            due = "" if payload.due is None else f", debited on {_day(day=payload.due)}"
            note = f"{payload.card_name} statement {payload.period}{due}"
    return {**spec, "footnote": _sentence(text=note)}


def _sentence(text: str) -> str:
    # A day such as 23.12. ends its sentence with its own dot.
    return f"{text.removesuffix('.')}."


def _bills_table(rows: list[BillRow], count: int, total: Decimal) -> dict[str, Any]:
    return _table(
        columns=[
            _column(key="due", label="Due", kind="date"),
            _column(key="payee", label="Payee"),
            _column(key="amount", label="Amount", kind="currency"),
        ],
        rows=[
            {"due": row.due.isoformat(), "payee": row.payee, "amount": float(row.amount_chf)}
            for row in rows
        ],
        count=count,
        footer={"payee": "Total", "amount": float(total)},
        noun="payments",
    )


def _table(
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
    count: int,
    footer: dict[str, Any],
    noun: str,
) -> dict[str, Any]:
    shown = rows[:TABLE_ROWS_MAX]
    spec = {"type": "table", "currency": "CHF", "columns": columns, "rows": shown, "footer": footer}
    # The total is of everything; a table that shows a part says so.
    if len(shown) < count:
        label_key = next(key for key, value in footer.items() if value == "Total")
        footer[label_key] = f"Total of all {count}"
        spec["footnote"] = f"{len(shown)} of {count} {noun} shown."
    return spec


def _column(key: str, label: str, kind: str = "text") -> dict[str, str]:
    return {"key": key, "label": label, "format": kind}


def _bar(title: str, data: list[dict[str, Any]], footnote: str) -> dict[str, Any]:
    return {
        "type": "bar",
        "currency": "CHF",
        "title": title,
        "x_label": "Month",
        "data": data,
        "footnote": footnote,
    }


def _booking_ids(source: Source) -> list[str]:
    if source.kind != "bookings":
        return []
    # A card statement's rows are card purchases, which the e-banking cannot open.
    return [row.id for row in source.rows if row.id.startswith("BK-")]


def _day(day: date) -> str:
    return f"{day.day:02d}.{day.month:02d}."


def _chf(amount: Decimal) -> str:
    return f"CHF {amount:,.2f}".replace(",", "'")
