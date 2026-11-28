from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TilePublication(BaseModel):
    tile_id: UUID
    dashboard_id: str
    dashboard_widget_id: str


class RequestTilePublicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The dashboard the customer is on (the host's `dashboard_id`); None means the default one.
    dashboard_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class ResponseTilePublication(BaseModel):
    tile_id: UUID
    dashboard_id: str
    dashboard_widget_id: str
