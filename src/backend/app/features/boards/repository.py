from uuid import UUID

from sqlalchemy import func, select, update

from app.core.repository import BaseRepository
from app.features.boards.models import BoardORM, BoardPlanORM, BoardTileORM
from app.features.boards.schemas import Board, BoardPlan, Tile


class BoardRepository(BaseRepository[BoardORM, Board]):
    orm_model = BoardORM
    schema = Board
    sortable_fields = frozenset({"created_at", "position"})
    default_sort = "position"

    async def get_owned(self, board_id: UUID, owner_id: UUID) -> Board | None:
        stmt = select(BoardORM).filter_by(id=board_id, owner_id=owner_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None

    async def close_read(self) -> None:
        # Ends the reads' transaction, so none stays open across a model call.
        await self.session.commit()

    async def count_owned(self, owner_id: UUID) -> int:
        stmt = select(func.count()).select_from(BoardORM).where(BoardORM.owner_id == owner_id)
        return await self.session.scalar(stmt) or 0

    async def count_tiles(self, board_ids: list[UUID]) -> dict[UUID, int]:
        stmt = (
            select(BoardTileORM.board_id, func.count())
            .where(BoardTileORM.board_id.in_(board_ids))
            .group_by(BoardTileORM.board_id)
        )
        rows = await self.session.execute(stmt)
        return {board_id: count for board_id, count in rows}

    async def rename(self, board_id: UUID, name: str) -> Board | None:
        row = await self.session.get(BoardORM, board_id)
        if row is None:
            return None
        row.name = name
        await self.session.commit()
        return self._to_schema(row=row)

    async def set_positions(self, ordered_ids: list[UUID]) -> None:
        for position, board_id in enumerate(ordered_ids):
            await self.session.execute(
                update(BoardORM).where(BoardORM.id == board_id).values(position=position)
            )
        await self.session.commit()


class TileRepository(BaseRepository[BoardTileORM, Tile]):
    orm_model = BoardTileORM
    schema = Tile
    sortable_fields = frozenset({"created_at", "position"})
    default_sort = "position"

    async def get_in_board(self, tile_id: UUID, board_id: UUID) -> Tile | None:
        stmt = select(BoardTileORM).filter_by(id=tile_id, board_id=board_id)
        row = await self.session.scalar(stmt)
        return self._to_schema(row=row) if row is not None else None

    async def count_in_board(self, board_id: UUID) -> int:
        stmt = select(func.count()).select_from(BoardTileORM).where(
            BoardTileORM.board_id == board_id
        )
        return await self.session.scalar(stmt) or 0

    async def retitle(self, tile_id: UUID, title: str) -> Tile | None:
        row = await self.session.get(BoardTileORM, tile_id)
        if row is None:
            return None
        row.title = title
        await self.session.commit()
        return self._to_schema(row=row)

    async def set_positions(self, ordered_ids: list[UUID]) -> None:
        for position, tile_id in enumerate(ordered_ids):
            await self.session.execute(
                update(BoardTileORM).where(BoardTileORM.id == tile_id).values(position=position)
            )
        await self.session.commit()


class BoardPlanRepository(BaseRepository[BoardPlanORM, BoardPlan]):
    orm_model = BoardPlanORM
    schema = BoardPlan
