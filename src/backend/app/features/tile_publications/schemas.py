from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TilePublication(BaseModel):
    tile_id: UUID
    dashboard_id: str
    dashboard_widget_id: str


class TileSnapshot(BaseModel):
    """The tile as the page draws it: one HTML document, and the room it needs on the grid."""

    model_config = ConfigDict(extra="forbid")

    # The limits are the banking API's own for an `html` widget.
    html: str = Field(min_length=1, max_length=480_000)
    height: int = Field(ge=80, le=1200)
    columns: int = Field(ge=1, le=3)


class RequestTilePublicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The dashboard the customer is on (the host's `dashboard_id`); None means the default one.
    dashboard_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    # Without a snapshot the widget is drawn by the e-banking from the tile's figures.
    snapshot: TileSnapshot | None = None


class ResponseTilePublication(BaseModel):
    tile_id: UUID
    dashboard_id: str
    dashboard_widget_id: str
