from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.features.boards.repository import BoardPlanRepository, BoardRepository, TileRepository
from app.features.boards.schemas import Board, Tile
from app.features.boards.service import BoardService
from app.features.conversations.dependencies import ConversationServiceDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.tiles.dependencies import TileServiceDep


def get_board_service(
    session: SessionDep, tile_service: TileServiceDep, conversations: ConversationServiceDep
) -> BoardService:
    return BoardService(
        boards=BoardRepository(session=session),
        tiles=TileRepository(session=session),
        plans=BoardPlanRepository(session=session),
        tile_service=tile_service,
        conversations=conversations,
    )


BoardServiceDep = Annotated[BoardService, Depends(get_board_service)]


async def get_owned_board(
    board_id: UUID, user: CurrentUserDep, service: BoardServiceDep
) -> Board:
    return await service.get_board(board_id=board_id, owner_id=user.id)


OwnedBoardDep = Annotated[Board, Depends(get_owned_board)]


async def get_board_tile(tile_id: UUID, board: OwnedBoardDep, service: BoardServiceDep) -> Tile:
    return await service.get_tile(board_id=board.id, tile_id=tile_id)


BoardTileDep = Annotated[Tile, Depends(get_board_tile)]


async def get_today(ledger: LedgerServiceDep) -> date:
    return await ledger.get_today()


TodayDep = Annotated[date, Depends(get_today)]
