"""link conversations to boards

Revision ID: b7c1d2e3f4a5
Revises: 983c25428fa6
Create Date: 2026-11-28 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "983c25428fa6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """A board has many conversations, so the link moves from the board to the conversation."""
    op.add_column("conversations", sa.Column("board_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_conversations_board_id"), "conversations", ["board_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_conversations_board_id_boards"),
        "conversations",
        "boards",
        ["board_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        "UPDATE conversations SET board_id = boards.id FROM boards "
        "WHERE boards.conversation_id = conversations.id"
    )
    op.drop_column("boards", "conversation_id")


def downgrade() -> None:
    """Each board gets its oldest conversation back."""
    op.add_column("boards", sa.Column("conversation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_boards_conversation_id_conversations"),
        "boards",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE boards SET conversation_id = ("
        "SELECT id FROM conversations WHERE board_id = boards.id ORDER BY created_at LIMIT 1)"
    )
    op.drop_constraint(
        op.f("fk_conversations_board_id_boards"), "conversations", type_="foreignkey"
    )
    op.drop_index(op.f("ix_conversations_board_id"), table_name="conversations")
    op.drop_column("conversations", "board_id")
