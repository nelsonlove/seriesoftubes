"""Add progress column to executions

Revision ID: 282f82529b59
Revises:
Create Date: 2025-06-26 23:57:05.390257

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "282f82529b59"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "executions",
        sa.Column("progress", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("executions", "progress")
