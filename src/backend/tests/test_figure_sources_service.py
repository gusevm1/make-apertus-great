from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.provenance import FigureRow
from app.features.figure_checks.service import FigureCheckService
from app.features.figure_sources.service import FigureSourceService
from app.features.ledger.service import LedgerService
from app.features.tool_calls.schemas import ToolCall
from tests.conftest import CUSTOMER_TOKEN, fake_banking_client


def service() -> FigureSourceService:
    return FigureSourceService(
        figure_checks=FigureCheckService(),
        ledger=LedgerService(banking=fake_banking_client()),
        token=CUSTOMER_TOKEN,
    )


def call(tool_name: str, title: str, result: dict[str, Any]) -> ToolCall:
    return ToolCall(
        id=uuid4(),
        conversation_id=uuid4(),
        message_id=uuid4(),
        position=0,
        round=0,
        plan="",
        reason="",
        tool_name=tool_name,
        title=title,
        icon="",
        arguments={},
        result=result,
        error=None,
        provenance=None,
        created_at=datetime.now(UTC),
    )


async def test_a_month_sum_names_its_bookings_from_the_ledger() -> None:
    sums = call(
        tool_name="sum_by_month",
        title="Spending per month",
        result={
            "months": [{"month": "2026-10", "money_out_chf": "-3012.10", "count": 2}],
            "row_ids": {"2026-10": ["BK-00101", "BK-00102"]},
            "total_sentence": "CHF 3'012.10 went out in 2 bookings.",
        },
    )

    [source] = await service().figure_sources(
        answer="Im Oktober gingen CHF 3'012.10 hinaus.", calls=[sums], documents=[]
    )

    assert source.text == "3'012.10"
    assert source.label == "Spending per month, 2026-10"
    assert source.tool_call_id == str(sums.id)
    assert source.count == 2
    assert [row.id for row in source.rows] == ["BK-00101", "BK-00102"]
    assert source.rows[0] == FigureRow(
        id="BK-00101",
        date="2026-10-30",
        text="Kartenzahlung Debit Mastercard 30.10.2026 MIGROS",
        amount_chf="-212.1",
    )


async def test_a_single_amount_names_its_own_booking() -> None:
    search = call(
        tool_name="search_movements",
        title="Bookings at Migros",
        result={
            "rows": [
                {
                    "id": "BK-00101",
                    "date": "2026-10-30",
                    "text": "MIGROS BERN",
                    "amount_chf": "-212.10",
                }
            ],
            "row_ids": ["BK-00101"],
        },
    )

    [source] = await service().figure_sources(
        answer="Bei Migros hast du CHF 212.10 bezahlt.", calls=[search], documents=[]
    )

    assert source.count == 1
    assert source.rows == [
        FigureRow(id="BK-00101", date="2026-10-30", text="MIGROS BERN", amount_chf="-212.10")
    ]


async def test_a_price_from_the_web_names_its_page() -> None:
    search = call(
        tool_name="search_web",
        title="Web search",
        result={
            "query": "Swisscom Abo unter 30",
            "results": [
                {
                    "title": "blue Mobile M young",
                    "url": "https://www.swisscom.ch/young",
                    "snippet": "Unter 30 nur CHF 35.90 im Monat.",
                }
            ],
            "sources": [{"title": "blue Mobile M young", "url": "https://www.swisscom.ch/young"}],
        },
    )

    [source] = await service().figure_sources(
        answer="Das Abo kostet CHF 35.90 im Monat.", calls=[search], documents=[]
    )

    assert source.label == "blue Mobile M young"
    assert source.url == "https://www.swisscom.ch/young"
    assert source.rows == []


async def test_a_figure_in_no_source_gets_none_and_the_newest_call_wins() -> None:
    older = call(tool_name="sum_by_month", title="Older", result={"total_chf": "50.00"})
    newer = call(tool_name="sum_by_month", title="Newer", result={"total_chf": "50.00"})

    sources = await service().figure_sources(
        answer="Es waren CHF 50.00, nicht CHF 77.00.", calls=[older, newer], documents=[]
    )

    assert [(source.text, source.label) for source in sources] == [("50.00", "Newer")]
