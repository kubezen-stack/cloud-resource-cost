"""test

Revision ID: 2cb2e21a092e
Revises: 2f73cd22b315
Create Date: 2026-04-30 14:53:22.863842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2cb2e21a092e'
down_revision: Union[str, Sequence[str], None] = '2f73cd22b315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
