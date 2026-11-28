from typing import Any, cast
from uuid import UUID

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.board_plans.service import BoardPlanService
from app.features.boards.repository import BoardPlanRepository, BoardRepository, TileRepository
from app.features.boards.service import BoardService
from app.features.conversations.service import ConversationService
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.service import TileService
from tests.conftest import BANK_WRITES, CUSTOMER_TOKEN, DASHBOARDS, TODAY, fake_banking_client


async def _tile(client: httpx2.AsyncClient) -> tuple[str, str]:
    board = (await client.post("/api/boards", json={"name": "Mine"})).json()
    created = await client.post(
        f"/api/boards/{board['id']}/tiles",
        json={"template": "monthly_spending", "args": {}},
    )
    assert created.status_code == 201, created.text
    return board["id"], created.json()["id"]


SNAPSHOT = {
    "html": '<!doctype html><body><article class="tile"></article></body>',
    "height": 260,
    "columns": 2,
}


async def _publish(client: httpx2.AsyncClient, board_id: str, tile_id: str) -> httpx2.Response:
    return await client.post(
        f"/api/boards/{board_id}/tiles/{tile_id}/publications", json={"snapshot": SNAPSHOT}
    )


async def test_a_published_tile_is_an_html_widget_that_names_the_tile_to_frame(
    client: httpx2.AsyncClient,
) -> None:
    board_id, tile_id = await _tile(client=client)

    published = await _publish(client=client, board_id=board_id, tile_id=tile_id)

    assert published.status_code == 201
    assert published.json()["dashboard_widget_id"] == "W-0010"
    ((method, path, body),) = BANK_WRITES
    assert (method, path) == ("POST", "/dashboards/DASH-01/widgets")
    custom = body["custom"]
    assert custom["format"] == "html"
    # The e-banking frames the live tile named here; the drawing after it is the fallback.
    assert custom["html"] == f"<!-- trustroom-tile:{board_id}/{tile_id} -->{SNAPSHOT['html']}"
    assert custom["height"] == SNAPSHOT["height"]
    assert body["position"]["width"] == SNAPSHOT["columns"]
    assert CUSTOMER_TOKEN not in custom["html"]


async def test_publishing_again_replaces_the_widget(
    client: httpx2.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_id, tile_id = await _tile(client=client)
    await _publish(client=client, board_id=board_id, tile_id=tile_id)
    (_, _, first) = BANK_WRITES[0]
    widget: dict[str, Any] = {"id": "W-0010", **first}
    monkeypatch.setitem(DASHBOARDS[1], "widgets", [widget])

    republished = await _publish(client=client, board_id=board_id, tile_id=tile_id)

    assert republished.json()["dashboard_widget_id"] == "W-0010"
    method, path, body = BANK_WRITES[-1]
    assert (method, path) == ("PATCH", "/dashboards/DASH-01/widgets/W-0010")
    assert body["custom"]["format"] == "html"
    assert len(BANK_WRITES) == 2


async def test_a_changed_tile_keeps_its_id_so_its_widget_shows_the_change(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    board_id, tile_id = await _tile(client=client)
    ledger = LedgerService(banking=fake_banking_client())
    boards = BoardService(
        boards=BoardRepository(session=session),
        tiles=TileRepository(session=session),
        plans=BoardPlanRepository(session=session),
        tile_service=TileService(ledger=ledger, recurring=RecurringPaymentService(ledger=ledger)),
        conversations=cast(ConversationService, None),
        planner=cast(BoardPlanService, None),
    )
    tile = await boards.get_tile(board_id=UUID(board_id), tile_id=UUID(tile_id))

    changed, _ = await boards.change_tile(
        tile=tile, args={"months": 12}, token=CUSTOMER_TOKEN, today=TODAY
    )

    assert changed.id == tile.id
    shown = (await client.get(f"/api/boards/{board_id}/tiles/{tile_id}")).json()
    assert shown["args"] == {"months": 12}
    assert shown["payload"]["template"] == "monthly_spending"
