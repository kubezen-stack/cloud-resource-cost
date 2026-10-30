"""add_cost_anomalies

Revision ID: c4d8f1a92b7e
Revises: 2b222c320e48
Create Date: 2026-10-30 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c4d8f1a92b7e'
down_revision: Union[str, Sequence[str], None] = '2b222c320e48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cost_anomalies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aws_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_name', sa.String(), nullable=False),
        sa.Column('anomaly_date', sa.Date(), nullable=False),
        sa.Column('actual_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('expected_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('deviation_pct', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('anomaly_score', sa.Float(), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['aws_account_id'], ['aws_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aws_account_id', 'service_name', 'anomaly_date', name='uq_cost_anomaly_account_service_date'),
    )
    op.create_index(op.f('ix_cost_anomalies_id'), 'cost_anomalies', ['id'], unique=False)
    op.create_index('ix_cost_anomalies_account_date', 'cost_anomalies', ['aws_account_id', 'anomaly_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_cost_anomalies_account_date', table_name='cost_anomalies')
    op.drop_index(op.f('ix_cost_anomalies_id'), table_name='cost_anomalies')
    op.drop_table('cost_anomalies')
