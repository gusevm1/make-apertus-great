from datetime import date
from typing import Any
from urllib.parse import quote

from app.core.errors import NotFoundError
from app.features.boards.schemas import Tile
from app.features.boards.service import BoardService
from app.features.ledger.service import LedgerService
from app.features.payments.service import PaymentService
from app.features.tile_publications.mapping import tile_marker, widget_of
from app.features.tile_publications.schemas import TilePublication


class TilePublicationService:
    def __init__(
        self, boards: BoardService, ledger: LedgerService, payments: PaymentService
    ) -> None:
        self.boards = boards
        self.ledger = ledger
        self.payments = payments

    async def publish_tile(
        self, tile: Tile, dashboard_id: str | None, token: str, today: date
    ) -> TilePublication:
        """Put the tile as it is now on the dashboard after the click, replacing an older copy."""
        payload = await self.boards.resolve_tile(tile=tile, token=token, today=today)
        widget = widget_of(payload=payload, title=tile.title, tile_id=tile.id, today=today)
        dashboard = await self._dashboard(dashboard_id=dashboard_id, token=token)
        path = f"/dashboards/{quote(dashboard['id'], safe='')}/widgets"
        marker = tile_marker(tile_id=tile.id)
        widget_id = next(
            (
                item["id"]
                for item in dashboard["widgets"]
                if (item.get("custom") or {}).get("prompt") == marker
            ),
            None,
        )
        if widget_id is None:
            created = await self.payments.write(
                method="POST", path=path, token=token, body={"type": "custom", **widget}
            )
            widget_id = created.root["id"]
        else:
            await self.payments.write(
                method="PATCH",
                path=f"{path}/{quote(widget_id, safe='')}",
                token=token,
                body=widget,
            )
        return TilePublication(
            tile_id=tile.id, dashboard_id=dashboard["id"], dashboard_widget_id=widget_id
        )

    async def _dashboard(self, dashboard_id: str | None, token: str) -> dict[str, Any]:
        items = (await self.ledger.read(path="/dashboards", token=token))["items"]
        if dashboard_id is not None:
            found = next((item for item in items if item["id"] == dashboard_id), None)
            if found is None:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            return found
        if len(items) == 0:
            raise NotFoundError("Your e-banking has no dashboard yet")
        return next((item for item in items if item["is_default"]), items[0])
