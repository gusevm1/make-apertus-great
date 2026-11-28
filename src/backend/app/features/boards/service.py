import asyncio
import logging
from datetime import date
from uuid import UUID

from app.core.errors import BadRequestError, NotFoundError
from app.features.boards.repository import BoardPlanRepository, BoardRepository, TileRepository
from app.features.boards.schemas import (
    DEFAULT_BOARD_NAME,
    ABOUT_NAME_WORDS,
    Board,
    BoardPlan,
    BoardSummary,
    RequestBoardCreate,
    Tile,
)
from app.features.conversations.schemas import RequestConversationCreate
from app.features.conversations.service import ConversationService
from app.features.tiles.schemas import AnyPayload
from app.features.tiles.service import TileError, TileService

logger = logging.getLogger(__name__)

UNLOADABLE_REASON = "This tile could not be loaded"


def _moved(ids: list[UUID], moved_id: UUID, position: int) -> list[UUID]:
    rest = [item for item in ids if item != moved_id]
    rest.insert(min(position, len(rest)), moved_id)
    return rest


class BoardService:
    def __init__(
        self,
        boards: BoardRepository,
        tiles: TileRepository,
        plans: BoardPlanRepository,
        tile_service: TileService,
        conversations: ConversationService,
    ) -> None:
        self.boards = boards
        self.tiles = tiles
        self.plans = plans
        self.tile_service = tile_service
        self.conversations = conversations

    async def list_boards(self, owner_id: UUID) -> list[BoardSummary]:
        """List the customer's boards by position, with their tile counts."""
        boards = await self.boards.list(sort="position", owner_id=owner_id)
        counts = await self.boards.count_tiles(board_ids=[board.id for board in boards])
        return [BoardSummary(board=board, tile_count=counts.get(board.id, 0)) for board in boards]

    async def get_board(self, board_id: UUID, owner_id: UUID) -> Board:
        """Return the customer's board; someone else's counts as not found."""
        board = await self.boards.get_owned(board_id=board_id, owner_id=owner_id)
        if board is None:
            raise NotFoundError("Board not found")
        return board

    async def get_tile(self, board_id: UUID, tile_id: UUID) -> Tile:
        """Return a tile of the board."""
        tile = await self.tiles.get_in_board(tile_id=tile_id, board_id=board_id)
        if tile is None:
            raise NotFoundError("Tile not found")
        return tile

    async def create_board(self, owner_id: UUID, data: RequestBoardCreate, token: str) -> Board:
        """Create a board at the end with a conversation of its own."""
        # Seam: the next wave lets the model fill the board from `data.about`, using `token`.
        name = self._board_name(data=data)
        conversation = await self.conversations.create_conversation(
            data=RequestConversationCreate(title=name), owner_id=owner_id
        )
        position = await self.boards.count_owned(owner_id=owner_id)
        return await self.boards.create(
            owner_id=owner_id, name=name, position=position, conversation_id=conversation.id
        )

    async def rename_board(self, board_id: UUID, name: str) -> Board:
        """Change the board's name."""
        board = await self.boards.rename(board_id=board_id, name=name)
        if board is None:
            raise NotFoundError("Board not found")
        return board

    async def move_board(self, board: Board, position: int) -> None:
        """Move the board to a 0-based index among the customer's boards."""
        boards = await self.boards.list(sort="position", owner_id=board.owner_id)
        ids = _moved(ids=[item.id for item in boards], moved_id=board.id, position=position)
        await self.boards.set_positions(ordered_ids=ids)

    async def delete_board(self, board: Board) -> None:
        """Delete the board, its tiles and its conversation."""
        await self.boards.delete(entity_id=board.id)
        await self.boards.set_positions(
            ordered_ids=[
                item.id for item in await self.boards.list(sort="position", owner_id=board.owner_id)
            ]
        )
        if board.conversation_id is not None:
            await self.conversations.delete_conversation(conversation_id=board.conversation_id)

    async def add_tile(
        self,
        board_id: UUID,
        template: str,
        args: dict,
        title: str | None,
        position: int | None,
        token: str,
        today: date,
    ) -> tuple[Tile, AnyPayload]:
        """Check the arguments, resolve once, then store the tile; nothing is stored on a TileError."""
        try:
            validated = self.tile_service.validate_args(template=template, args=args)
            payload = await self.tile_service.resolve(
                template=template,
                args=validated.model_dump(mode="json", exclude_none=True),
                token=token,
                today=today,
            )
        except TileError as error:
            raise BadRequestError(str(error)) from error
        tile = await self.tiles.create(
            board_id=board_id,
            template=template,
            args=validated.model_dump(mode="json", exclude_none=True),
            title=title if title is not None else self.tile_service.default_title(payload=payload),
            position=await self.tiles.count_in_board(board_id=board_id),
        )
        if position is not None:
            await self.move_tile(tile=tile, position=position)
            tile = await self.get_tile(board_id=board_id, tile_id=tile.id)
        return tile, payload

    async def rename_tile(self, tile: Tile, title: str) -> Tile:
        """Change the tile's title."""
        renamed = await self.tiles.retitle(tile_id=tile.id, title=title)
        if renamed is None:
            raise NotFoundError("Tile not found")
        return renamed

    async def move_tile(self, tile: Tile, position: int) -> None:
        """Move the tile to a 0-based index in its board."""
        tiles = await self.tiles.list(sort="position", board_id=tile.board_id)
        ids = _moved(ids=[item.id for item in tiles], moved_id=tile.id, position=position)
        await self.tiles.set_positions(ordered_ids=ids)

    async def remove_tile(self, tile: Tile) -> None:
        """Delete the tile and close the gap."""
        await self.tiles.delete(entity_id=tile.id)
        remaining = await self.tiles.list(sort="position", board_id=tile.board_id)
        await self.tiles.set_positions(ordered_ids=[item.id for item in remaining])

    async def resolve_tile(self, tile: Tile, token: str, today: date) -> AnyPayload:
        """Compute one stored tile as it is now."""
        try:
            return await self.tile_service.resolve(
                template=tile.template, args=tile.args, token=token, today=today
            )
        except TileError as error:
            raise BadRequestError(str(error)) from error

    async def get_board_resolved(
        self, board: Board, token: str, today: date
    ) -> tuple[list[tuple[Tile, AnyPayload]], list[tuple[Tile, str]]]:
        """Resolve every tile in parallel; a tile that cannot be drawn is returned as dropped with a reason."""
        tiles = await self.tiles.list(sort="position", board_id=board.id)
        results = await asyncio.gather(
            *(
                self.tile_service.resolve(
                    template=tile.template, args=tile.args, token=token, today=today
                )
                for tile in tiles
            ),
            return_exceptions=True,
        )
        resolved: list[tuple[Tile, AnyPayload]] = []
        dropped: list[tuple[Tile, str]] = []
        for tile, result in zip(tiles, results, strict=True):
            if isinstance(result, TileError):
                dropped.append((tile, str(result)))
            elif isinstance(result, BaseException):
                logger.error("Tile %s could not be loaded", tile.id, exc_info=result)
                dropped.append((tile, UNLOADABLE_REASON))
            else:
                resolved.append((tile, result))
        return resolved, dropped

    async def list_board_plans(self, owner_id: UUID) -> list[BoardPlan]:
        """List the customer's board plans, newest first."""
        return await self.plans.list(owner_id=owner_id)

    @staticmethod
    def _board_name(data: RequestBoardCreate) -> str:
        if data.name is not None and data.name.strip() != "":
            return data.name.strip()
        if data.about is not None and data.about.split():
            return " ".join(data.about.split()[:ABOUT_NAME_WORDS])[:80]
        return DEFAULT_BOARD_NAME
