"""initial tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # accounts
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('overdraft_limit', sa.Numeric(), nullable=True, server_default='0')
    )

    # ledger_entries
    op.create_table(
        'ledger_entries',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('account_id', sa.Integer, nullable=False, index=True),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('amount', sa.Numeric, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('tx_id', sa.String(), nullable=False, index=True),
    )

    # outbox_events
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('tx_id', sa.String(), nullable=False, index=True),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('attempts', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer, nullable=False, server_default='5'),
        sa.Column('locked', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # balance_snapshots
    op.create_table(
        'balance_snapshots',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('account_id', sa.Integer, nullable=False, index=True),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('balance', sa.Numeric, nullable=False),
        sa.Column('snapshot_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_entry_id', sa.BigInteger, nullable=True),
    )


def downgrade():
    op.drop_table('balance_snapshots')
    op.drop_table('outbox_events')
    op.drop_table('ledger_entries')
    op.drop_table('accounts')
