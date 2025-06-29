"""Add error_details field to executions

Revision ID: c8283a587f70
Revises: a15dbfb85e3e
Create Date: 2025-06-29 01:07:33.052235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8283a587f70'
down_revision: Union[str, None] = 'a15dbfb85e3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('executions', sa.Column('error_details', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('executions', 'error_details')
