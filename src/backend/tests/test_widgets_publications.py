from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.widgets import service as widget_service
from app.features.widgets.models import WidgetORM, WidgetVersionORM
from app.features.widgets.repository import WidgetRepository
from tests.conftest import BANK_WRITES
from tests.factories import DEMO_USER_ID, make_conversation

SPEC = {
    "title": "Spending per month",
    "body": {"type": "bar_chart", "data": "months", "x": "month", "y": "money_out_chf"},
}
DATA = {
    "months": [
        {"month": "2026-09", "money_out_chf": 17273.6, "booking_ids": ["BK-01", "BK-02"]},
        {"month": "2026-10", "money_out_chf": 10598.77, "booking_ids": ["BK-03", "BK-01"]},
    ]
}


def _version(number: int) -> dict[str, Any]:
    return {
        "number": number,
        "spec": SPEC,
        "data": DATA,
        "request": "Show my spending per month as a chart.",
        "model": "apertus-70b",
        "latency_ms": 3500,
        "tool_call_ids": [],
        "checks": [],
    }


async def _widget(session: AsyncSession, owner_id: UUID = DEMO_USER_ID) -> UUID:
    conversation = await make_conversation(session=session, owner_id=owner_id)
    widget, _ = await WidgetRepository(session=session).create_with_version(
        widget={
            "owner_id": owner_id,
            "conversation_id": conversation.id,
            "title": "Spending per month",
            "current_version": 1,
        },
        version=_version(number=1),
    )
    return widget.id


async def _publish(client: httpx2.AsyncClient, widget_id: UUID, **body: Any) -> httpx2.Response:
    return await client.post(f"/api/widgets/{widget_id}/publications", json=body)


async def test_a_widget_goes_to_the_default_dashboard_as_its_static_page(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    widget_id = await _widget(session=session)

    published = await _publish(client=client, widget_id=widget_id)

    assert published.status_code == 201
    assert published.json() == {
        "widget_id": str(widget_id),
        "version_number": 1,
        "dashboard_id": "DASH-01",
        "dashboard_widget_id": "W-0010",
    }
    ((method, path, body),) = BANK_WRITES
    assert (method, path) == ("POST", "/dashboards/DASH-01/widgets")
    assert body["type"] == "custom"
    assert body["title"] == "Spending per month"
    custom = body["custom"]
    assert custom["format"] == "html"
    assert 'http-equiv="Content-Security-Policy"' in custom["html"]
    assert 'data-form="static"' in custom["html"]
    assert 80 <= custom["height"] <= 1200
    assert custom["source"] == {"booking_ids": ["BK-01", "BK-02", "BK-03"]}
    assert custom["prompt"] == "Show my spending per month as a chart."
    assert custom["created_by"] == "TrustRoom"
    version = (await client.get(f"/api/widgets/{widget_id}/versions/1")).json()
    assert version["published_version"] == 1


async def test_the_dashboard_the_customer_is_on_gets_the_widget(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    widget_id = await _widget(session=session)

    published = await _publish(client=client, widget_id=widget_id, dashboard_id="DASH-02")

    assert published.json()["dashboard_id"] == "DASH-02"
    assert BANK_WRITES[0][1] == "/dashboards/DASH-02/widgets"


async def test_a_newer_version_replaces_the_tile_instead_of_adding_one(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    widget_id = await _widget(session=session)
    await _publish(client=client, widget_id=widget_id)
    session.add(WidgetVersionORM(widget_id=widget_id, **_version(number=2)))
    widget = await session.get(WidgetORM, widget_id)
    assert widget is not None
    widget.current_version = 2
    await session.commit()

    republished = await _publish(client=client, widget_id=widget_id)

    assert republished.status_code == 201
    assert republished.json()["version_number"] == 2
    assert republished.json()["dashboard_widget_id"] == "W-0010"
    method, path, body = BANK_WRITES[-1]
    assert (method, path) == ("PATCH", "/dashboards/DASH-01/widgets/W-0010")
    assert "type" not in body
    assert body["custom"]["format"] == "html"
    assert len(BANK_WRITES) == 2


async def test_a_tile_the_customer_removed_is_added_again(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    widget_id = await _widget(session=session)
    await WidgetRepository(session=session).set_publication(
        widget_id=widget_id, dashboard_id="DASH-01", dashboard_widget_id="W-GONE", version_number=1
    )

    published = await _publish(client=client, widget_id=widget_id)

    assert published.status_code == 201
    assert [(method, path) for method, path, _ in BANK_WRITES] == [
        ("PATCH", "/dashboards/DASH-01/widgets/W-GONE"),
        ("POST", "/dashboards/DASH-01/widgets"),
    ]
    assert published.json()["dashboard_widget_id"] == "W-0010"


async def test_a_page_too_large_for_the_dashboard_never_reaches_the_bank(
    client: httpx2.AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    widget_id = await _widget(session=session)
    monkeypatch.setattr(widget_service, "DASHBOARD_HTML_MAX", 100)

    refused = await _publish(client=client, widget_id=widget_id)

    assert refused.status_code == 400
    assert "at most 100" in refused.json()["message"]
    assert BANK_WRITES == []


async def test_another_customers_widget_is_not_found(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    widget_id = await _widget(session=session, owner_id=uuid4())

    refused = await _publish(client=client, widget_id=widget_id)

    assert refused.status_code == 404
    assert BANK_WRITES == []


async def test_a_dashboard_id_that_could_leave_its_path_is_refused(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    widget_id = await _widget(session=session)

    refused = await _publish(client=client, widget_id=widget_id, dashboard_id="../admin")

    assert refused.status_code == 422
    assert BANK_WRITES == []


def test_a_tile_is_as_tall_as_the_components_it_stacks() -> None:
    kpi = {"type": "kpi"}
    chart = {"type": "bar_chart"}

    assert widget_service._tile_height(component=kpi) == 166
    assert widget_service._tile_height(component={"type": "stack", "children": [kpi, chart]}) == (
        166 + 356 + 2 * 16
    )
    many = {"type": "stack", "children": [chart] * 8}
    assert widget_service._tile_height(component=many) == 1200
