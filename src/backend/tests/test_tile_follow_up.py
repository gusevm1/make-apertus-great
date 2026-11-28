from datetime import UTC, datetime
from uuid import uuid4

from app.features.boards.schemas import Tile
from app.features.boards.tools import _free_title, _revised_tile

BOARD_ID = uuid4()


def tile(template: str, title: str, position: int) -> Tile:
    return Tile(
        id=uuid4(),
        board_id=BOARD_ID,
        template=template,
        args={},
        title=title,
        position=position,
        created_at=datetime.now(UTC),
    )


def test_the_same_kind_under_the_same_name_is_the_tile_it_changes() -> None:
    spending = tile(template="monthly_spending", title="Where the money goes", position=1)
    tiles = [tile(template="net_worth", title="What you own", position=0), spending]

    assert (
        _revised_tile(tiles=tiles, template="monthly_spending", title="where the money goes")
        == spending
    )
    assert (
        _revised_tile(tiles=tiles, template="merchant_spending", title="Where the money goes")
        is None
    )
    assert _revised_tile(tiles=tiles, template="monthly_spending", title="Restaurants") is None


def test_a_taken_title_gets_a_number() -> None:
    assert _free_title(title="Savings pots", taken=["What you own"]) == "Savings pots"
    assert _free_title(title="Savings pots", taken=["savings pots"]) == "Savings pots 2"
    assert (
        _free_title(title="Savings pots", taken=["Savings pots", "Savings pots 2"])
        == "Savings pots 3"
    )
