"""add worker lease fields

Revision ID: 3fb10de2af80
Revises: 28c11d119141
Create Date: 2026-08-20 16:02:39.805438

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3fb10de2af80"
down_revision: Union[str, Sequence[str], None] = "28c11d119141"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "analysis_runs",
        sa.Column(
            "worker_id",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "lease_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "analysis_runs",
        "lease_until",
    )

    op.drop_column(
        "analysis_runs",
        "worker_id",
    )