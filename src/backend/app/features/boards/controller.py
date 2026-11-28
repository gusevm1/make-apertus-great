from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import CurrentUserDep, require_user
from app.core.streaming import sse_response
from app.features.boards.dependencies import (
    BoardServiceDep,
    BoardTileDep,
    OwnedBoardDep,
    TodayDep,
)
from app.features.boards.schemas import (
    Board,
    BoardPlan,
    BoardSummary,
    RequestBoardCreate,
    RequestBoardUpdate,
    RequestTileCreate,
    RequestTileUpdate,
    ResponseBoard,
    ResponseBoardPlan,
    ResponseBoardSummary,
    ResponseDroppedTile,
    ResponseTile,
    Tile,
)
from app.features.conversations.schemas import ResponseConversation
from app.features.tiles.schemas import AnyPayload

router = APIRouter(prefix="/boards", tags=["boards"], dependencies=[Depends(require_user)])
plans_router = APIRouter(
    prefix="/board-plans", tags=["board-plans"], dependencies=[Depends(require_user)]
)


def _summary_response(board: Board, tile_count: int) -> ResponseBoardSummary:
    return ResponseBoardSummary(
        id=board.id,
        name=board.name,
        position=board.position,
        plan_id=board.plan_id,
        tile_count=tile_count,
    )


def _tile_response(tile: Tile, payload: AnyPayload) -> ResponseTile:
    return ResponseTile(
        id=tile.id,
        template=tile.template,
        title=tile.title,
        args=tile.args,
        position=tile.position,
        payload=payload,
    )


def _plan_response(plan: BoardPlan) -> ResponseBoardPlan:
    return ResponseBoardPlan.model_validate(plan, from_attributes=True)


def _built_response(built: tuple[BoardPlan, list[BoardSummary]]) -> ResponseBoardPlan:
    plan, summaries = built
    return _plan_response(plan=plan).model_copy(
        update={
            "boards": [
                _summary_response(board=summary.board, tile_count=summary.tile_count)
                for summary in summaries
            ]
        }
    )


async def _board_summary(
    board_id: UUID, user: CurrentUserDep, service: BoardServiceDep
) -> ResponseBoardSummary:
    summaries = await service.list_boards(owner_id=user.id)
    summary = next(item for item in summaries if item.board.id == board_id)
    return _summary_response(board=summary.board, tile_count=summary.tile_count)


def _board_response(
    board: Board, resolved: list[tuple[Tile, AnyPayload]], dropped: list[tuple[Tile, str]]
) -> ResponseBoard:
    return ResponseBoard(
        id=board.id,
        name=board.name,
        position=board.position,
        plan_id=board.plan_id,
        tiles=[_tile_response(tile=tile, payload=payload) for tile, payload in resolved],
        dropped=[
            ResponseDroppedTile(tile_id=tile.id, title=tile.title, reason=reason)
            for tile, reason in dropped
        ],
    )


@router.get("", response_model=list[ResponseBoardSummary])
async def list_boards(user: CurrentUserDep, service: BoardServiceDep) -> list[ResponseBoardSummary]:
    """List your boards in order."""
    summaries = await service.list_boards(owner_id=user.id)
    return [
        _summary_response(board=summary.board, tile_count=summary.tile_count)
        for summary in summaries
    ]


@router.post("", response_model=ResponseBoard, status_code=201)
async def create_board(
    body: RequestBoardCreate, user: CurrentUserDep, service: BoardServiceDep, today: TodayDep
) -> ResponseBoard:
    """Create a board with a conversation of its own; with `about`, the model fills it."""
    board = await service.create_board(owner_id=user.id, data=body, token=user.token, today=today)
    resolved, dropped = await service.get_board_resolved(board=board, token=user.token, today=today)
    return _board_response(board=board, resolved=resolved, dropped=dropped)


@router.get("/{board_id}", response_model=ResponseBoard)
async def get_board(
    board: OwnedBoardDep, user: CurrentUserDep, service: BoardServiceDep, today: TodayDep
) -> ResponseBoard:
    """Get a board with its tiles, computed from the banking API now."""
    resolved, dropped = await service.get_board_resolved(board=board, token=user.token, today=today)
    return _board_response(board=board, resolved=resolved, dropped=dropped)


@router.patch("/{board_id}", response_model=ResponseBoardSummary)
async def update_board(
    body: RequestBoardUpdate, board: OwnedBoardDep, user: CurrentUserDep, service: BoardServiceDep
) -> ResponseBoardSummary:
    """Rename a board or move it to a new place in the list."""
    if body.name is not None:
        await service.rename_board(board_id=board.id, name=body.name)
    if body.position is not None:
        await service.move_board(board=board, position=body.position)
    return await _board_summary(board_id=board.id, user=user, service=service)


@router.delete("/{board_id}", status_code=204)
async def delete_board(board: OwnedBoardDep, service: BoardServiceDep) -> None:
    """Delete a board with its tiles and its conversations."""
    await service.delete_board(board=board)


@router.post("/{board_id}/conversations", response_model=ResponseConversation, status_code=201)
async def create_board_conversation(
    board: OwnedBoardDep, service: BoardServiceDep
) -> ResponseConversation:
    """Start a new chat beside the board."""
    conversation = await service.create_conversation(board=board)
    return ResponseConversation.model_validate(conversation, from_attributes=True)


@router.post("/{board_id}/tiles", response_model=ResponseTile, status_code=201)
async def create_tile(
    body: RequestTileCreate,
    board: OwnedBoardDep,
    user: CurrentUserDep,
    service: BoardServiceDep,
    today: TodayDep,
) -> ResponseTile:
    """Add a tile, after checking that it can be drawn."""
    tile, payload = await service.add_tile(
        board_id=board.id,
        template=body.template,
        args=body.args,
        title=body.title,
        position=body.position,
        token=user.token,
        today=today,
    )
    return _tile_response(tile=tile, payload=payload)


@router.patch("/{board_id}/tiles/{tile_id}", response_model=ResponseTile)
async def update_tile(
    body: RequestTileUpdate,
    tile: BoardTileDep,
    user: CurrentUserDep,
    service: BoardServiceDep,
    today: TodayDep,
) -> ResponseTile:
    """Rename a tile or move it to a new place in the board."""
    if body.title is not None:
        await service.rename_tile(tile=tile, title=body.title)
    if body.position is not None:
        await service.move_tile(tile=tile, position=body.position)
    updated = await service.get_tile(board_id=tile.board_id, tile_id=tile.id)
    payload = await service.resolve_tile(tile=updated, token=user.token, today=today)
    return _tile_response(tile=updated, payload=payload)


@router.delete("/{board_id}/tiles/{tile_id}", status_code=204)
async def delete_tile(tile: BoardTileDep, service: BoardServiceDep) -> None:
    """Remove a tile from its board."""
    await service.remove_tile(tile=tile)


@plans_router.post("", response_model=ResponseBoardPlan, status_code=201)
async def create_board_plan(
    user: CurrentUserDep, service: BoardServiceDep, today: TodayDep, stream: bool = False
) -> ResponseBoardPlan | StreamingResponse:
    """Build your first boards from your own data; `?stream=true` sends each step as it runs."""
    if stream:
        events = service.stream_first_boards(owner_id=user.id, token=user.token, today=today)
        return sse_response(events=events, to_response=_built_response)
    built = await service.create_first_boards(owner_id=user.id, token=user.token, today=today)
    return _built_response(built=built)


@plans_router.get("", response_model=list[ResponseBoardPlan])
async def list_board_plans(
    user: CurrentUserDep, service: BoardServiceDep
) -> list[ResponseBoardPlan]:
    """List the plans behind your model-built boards, newest first."""
    plans = await service.list_board_plans(owner_id=user.id)
    return [_plan_response(plan=plan) for plan in plans]
