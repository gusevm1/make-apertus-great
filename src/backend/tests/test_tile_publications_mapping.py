from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.features.tile_publications.mapping import first_free_position, widget_of, widget_width
from app.features.tiles.schemas import (
    BillRow,
    BillsUntilPaydayPayload,
    MonthlySpendingPayload,
    NetWorthPayload,
    Source,
    SourceRow,
    SpendingMonth,
)

TODAY = date(2026, 11, 27)
NO_SOURCE = Source(label="8 payments", kind="payments", rows=[], count=0)


def bill(number: int) -> BillRow:
    return BillRow(
        id=f"PAY-{number}",
        due=date(2026, 12, number),
        payee=f"Payee {number}",
        detail=None,
        amount_chf=Decimal("100.10"),
        balance_after_chf=None,
        flag=None,
    )


def test_bills_become_a_table_of_eight_with_the_total_of_all() -> None:
    payload = BillsUntilPaydayPayload(
        figure_chf=Decimal("900.90"),
        source=NO_SOURCE,
        payday=date(2026, 12, 24),
        rows=[bill(number=number) for number in range(1, 10)],
    )
    tile_id = uuid4()

    widget = widget_of(payload=payload, title="Bills", tile_id=tile_id, today=TODAY)

    spec = widget["custom"]["spec"]
    assert widget["title"] == "Bills"
    assert widget["custom"]["prompt"] == f"trustroom-tile:{tile_id}"
    assert "source" not in widget["custom"]
    assert spec["type"] == "table"
    assert spec["subtitle"] == "As of 27.11."
    assert spec["rows"][0] == {"due": "2026-12-01", "payee": "Payee 1", "amount": 100.1}
    assert len(spec["rows"]) == 8
    assert spec["footer"] == {"payee": "Total of all 9", "amount": 900.9}
    assert spec["footnote"] == "8 of 9 payments shown."


def test_monthly_spending_becomes_a_bar_of_the_months() -> None:
    payload = MonthlySpendingPayload(
        figure_chf=Decimal("1500.00"),
        source=NO_SOURCE,
        months=[
            SpendingMonth(month="2026-09", total_chf=Decimal("1000.00"), count=3),
            SpendingMonth(month="2026-10", total_chf=Decimal("2000.00"), count=4),
        ],
        highest="2026-10",
    )

    spec = widget_of(payload=payload, title="Spending", tile_id=uuid4(), today=TODAY)["custom"][
        "spec"
    ]

    assert spec["type"] == "bar"
    assert spec["data"] == [
        {"label": "2026-09", "value": 1000.0},
        {"label": "2026-10", "value": 2000.0},
    ]
    assert spec["footnote"] == "On average CHF 1'500.00 per month."


def test_a_plain_kpi_links_only_its_booking_ids() -> None:
    payload = NetWorthPayload(
        figure_chf=Decimal("52000.50"),
        source=Source(
            label="3 bookings",
            kind="bookings",
            rows=[SourceRow(id=row_id, text="x") for row_id in ("BK-1", "CTX-2", "BK-3")],
            count=3,
        ),
        parts=[],
        includes_pension=False,
    )

    custom = widget_of(payload=payload, title="Worth", tile_id=uuid4(), today=TODAY)["custom"]

    assert custom["spec"]["type"] == "kpi"
    assert custom["spec"]["value"] == 52000.5
    assert "delta" not in custom["spec"]
    assert custom["source"] == {"booking_ids": ["BK-1", "BK-3"]}
    assert custom["spec"]["footnote"] == (
        "Without pillar 3a. The link opens only 2 of the 3 payments behind this tile."
    )


def box(col: int, row: int, width: int = 1) -> dict[str, dict[str, int]]:
    return {"position": {"col": col, "row": row, "width": width, "height": 1}}


def test_a_bills_table_is_two_wide_and_a_kpi_one() -> None:
    bills = BillsUntilPaydayPayload(
        figure_chf=Decimal("100.10"),
        source=NO_SOURCE,
        payday=date(2026, 12, 24),
        rows=[bill(number=1)],
    )
    kpi = NetWorthPayload(
        figure_chf=Decimal("1000"), source=NO_SOURCE, parts=[], includes_pension=False
    )

    assert (
        widget_width(widget=widget_of(payload=bills, title="B", tile_id=uuid4(), today=TODAY)) == 2
    )
    assert widget_width(widget=widget_of(payload=kpi, title="K", tile_id=uuid4(), today=TODAY)) == 1


def test_a_widget_takes_the_first_free_slot_row_by_row() -> None:
    dashboard = [box(0, 0), box(1, 0), box(2, 0), box(0, 1), box(1, 1, width=2), box(0, 2)]

    assert first_free_position(widgets=dashboard, width=1) == {
        "col": 1,
        "row": 2,
        "width": 1,
        "height": 1,
    }
    assert first_free_position(widgets=dashboard, width=2) == {
        "col": 1,
        "row": 2,
        "width": 2,
        "height": 1,
    }
    assert first_free_position(widgets=[*dashboard, box(2, 2)], width=2) == {
        "col": 0,
        "row": 3,
        "width": 2,
        "height": 1,
    }
