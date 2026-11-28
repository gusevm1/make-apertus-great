from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import CurrentUserDep
from app.core.db import SessionDep
from app.core.tools import TurnScope
from app.features.board_plans.dependencies import BoardPlanServiceDep
from app.features.boards import tools as board_tools
from app.features.boards.repository import BoardPlanRepository, BoardRepository, TileRepository
from app.features.boards.schemas import Board, Tile
from app.features.boards.service import BoardService
from app.features.context_entries.dependencies import ContextEntryServiceDep
from app.features.conversations.dependencies import ConversationServiceDep
from app.features.ledger.dependencies import LedgerServiceDep
from app.features.tiles.dependencies import TileServiceDep


def get_board_service(
    session: SessionDep,
    tile_service: TileServiceDep,
    conversations: ConversationServiceDep,
    planner: BoardPlanServiceDep,
) -> BoardService:
    return BoardService(
        boards=BoardRepository(session=session),
        tiles=TileRepository(session=session),
        plans=BoardPlanRepository(session=session),
        tile_service=tile_service,
        conversations=conversations,
        planner=planner,
    )


BoardServiceDep = Annotated[BoardService, Depends(get_board_service)]


async def get_owned_board(board_id: UUID, user: CurrentUserDep, service: BoardServiceDep) -> Board:
    return await service.get_board(board_id=board_id, owner_id=user.id)


OwnedBoardDep = Annotated[Board, Depends(get_owned_board)]


async def get_board_tile(tile_id: UUID, board: OwnedBoardDep, service: BoardServiceDep) -> Tile:
    return await service.get_tile(board_id=board.id, tile_id=tile_id)


BoardTileDep = Annotated[Tile, Depends(get_board_tile)]


async def get_today(ledger: LedgerServiceDep) -> date:
    return await ledger.get_today()


TodayDep = Annotated[date, Depends(get_today)]


type BoardTurns = Callable[[UUID | None, UUID | None], Awaitable[TurnScope | None]]


def get_board_turns(
    user: CurrentUserDep,
    service: BoardServiceDep,
    today: TodayDep,
    notes: ContextEntryServiceDep,
) -> BoardTurns:
    async def board_turn(board_id: UUID | None, tile_id: UUID | None) -> TurnScope | None:
        """The board tools of a message typed beside the customer's own board, or None."""
        if board_id is None:
            return None
        board = await service.get_board(board_id=board_id, owner_id=user.id)
        if tile_id is not None:
            await service.get_tile(board_id=board.id, tile_id=tile_id)
        active = await notes.list_entries(owner_id=user.id, status="active")
        return await board_tools.get_turn(
            service=service,
            board=board,
            tile_id=tile_id,
            owner_id=user.id,
            token=user.token,
            today=today,
            active_notes=[entry.text for entry in active],
        )

    return board_turn


BoardTurnsDep = Annotated[BoardTurns, Depends(get_board_turns)]
