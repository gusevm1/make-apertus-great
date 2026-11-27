"""describe documents

Revision ID: 3f1c2b7d9a41
Revises: dc9e85f8676d
Create Date: 2026-11-27 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3f1c2b7d9a41"
down_revision: str | Sequence[str] | None = "dc9e85f8676d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("kind", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("title", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("issuer", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("document_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("summary", sa.String(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "provenance")
    op.drop_column("documents", "fields")
    op.drop_column("documents", "summary")
    op.drop_column("documents", "document_date")
    op.drop_column("documents", "issuer")
    op.drop_column("documents", "title")
    op.drop_column("documents", "kind")
