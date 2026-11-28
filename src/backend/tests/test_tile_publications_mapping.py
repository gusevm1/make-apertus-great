from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.features.tile_publications.mapping import widget_of
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
