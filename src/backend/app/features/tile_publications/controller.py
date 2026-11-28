from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.boards.dependencies import BoardTileDep, TodayDep
from app.features.tile_publications.dependencies import TilePublicationServiceDep
from app.features.tile_publications.schemas import (
    RequestTilePublicationCreate,
    ResponseTilePublication,
)

router = APIRouter(
    prefix="/boards/{board_id}/tiles/{tile_id}/publications",
    tags=["tile-publications"],
    dependencies=[Depends(require_user)],
)


@router.post("", response_model=ResponseTilePublication, status_code=201)
async def create_tile_publication(
    body: RequestTilePublicationCreate,
    tile: BoardTileDep,
    user: CurrentUserDep,
    service: TilePublicationServiceDep,
    today: TodayDep,
) -> ResponseTilePublication:
    """Put a tile's figures on your e-banking dashboard, replacing its older copy."""
    publication = await service.publish_tile(
        tile=tile,
        dashboard_id=body.dashboard_id,
        snapshot=body.snapshot,
        token=user.token,
        today=today,
    )
    return ResponseTilePublication.model_validate(publication, from_attributes=True)
