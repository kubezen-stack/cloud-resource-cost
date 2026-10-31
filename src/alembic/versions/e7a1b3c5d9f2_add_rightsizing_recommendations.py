"""add_rightsizing_recommendations

Revision ID: e7a1b3c5d9f2
Revises: c4d8f1a92b7e
Create Date: 2026-10-31 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e7a1b3c5d9f2'
down_revision: Union[str, Sequence[str], None] = 'c4d8f1a92b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rightsizing_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aws_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('instance_id', sa.String(), nullable=False),
        sa.Column('instance_name', sa.String(), nullable=True),
        sa.Column('region', sa.String(), nullable=False),
        sa.Column('instance_type', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('recommended_type', sa.String(), nullable=True),
        sa.Column('estimated_savings_pct', sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column('cpu_avg', sa.Float(), nullable=True),
        sa.Column('cpu_p95', sa.Float(), nullable=True),
        sa.Column('cpu_max', sa.Float(), nullable=True),
        sa.Column('hours_observed', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['aws_account_id'], ['aws_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aws_account_id', 'instance_id', name='uq_rightsizing_account_instance'),
    )
    op.create_index(op.f('ix_rightsizing_recommendations_id'), 'rightsizing_recommendations', ['id'], unique=False)
    op.create_index('ix_rightsizing_account_action', 'rightsizing_recommendations', ['aws_account_id', 'action'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_rightsizing_account_action', table_name='rightsizing_recommendations')
    op.drop_index(op.f('ix_rightsizing_recommendations_id'), table_name='rightsizing_recommendations')
    op.drop_table('rightsizing_recommendations')
