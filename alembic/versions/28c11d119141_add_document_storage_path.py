"""add document storage path

Revision ID: 28c11d119141
Revises: b5479fec8584
Create Date: 2026-08-20 14:04:33.945243

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "28c11d119141"
down_revision: Union[str, Sequence[str], None] = "b5479fec8584"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "documents",
        sa.Column(
            "storage_path",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "documents",
        "storage_path",
    )