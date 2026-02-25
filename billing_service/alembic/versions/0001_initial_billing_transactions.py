"""Initial billing_transactions table

Revision ID: 0001
Revises:
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'billing_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('toll_event_id', sa.String(), nullable=False,
                  comment='Unique ID from the originating TollEvent'),
        sa.Column('vehicle_id', sa.String(), nullable=False,
                  comment='Vehicle identifier'),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False,
                  comment='Toll amount charged'),
        sa.Column('currency', sa.String(length=3), nullable=False,
                  comment='ISO currency code (e.g., USD)'),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='PENDING',
                  comment='PENDING, PROCESSING, SUCCESS, FAILED, RETRY'),
        sa.Column('transaction_time', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='Timestamp when record was created'),
        sa.Column('last_updated', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True,
                  comment='Timestamp of last update'),
        sa.Column('payment_gateway_ref', sa.String(), nullable=True,
                  comment='Reference ID from the payment provider'),
        sa.Column('payment_method_details', sa.String(), nullable=True,
                  comment='Masked details of payment method used'),
        sa.Column('error_message', sa.String(), nullable=True,
                  comment='Error message if transaction failed'),
        sa.Column('retry_count', sa.Integer(), nullable=False,
                  server_default='0', comment='Number of payment attempts'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_billing_transactions_id', 'billing_transactions', ['id'])
    op.create_index('ix_billing_transactions_toll_event_id', 'billing_transactions',
                    ['toll_event_id'], unique=True)
    op.create_index('ix_billing_transactions_vehicle_id', 'billing_transactions',
                    ['vehicle_id'])
    op.create_index('ix_billing_transactions_status', 'billing_transactions',
                    ['status'])
    op.create_index('ix_billing_transactions_payment_gateway_ref', 'billing_transactions',
                    ['payment_gateway_ref'])
    op.create_index('ix_billing_transactions_vehicle_status', 'billing_transactions',
                    ['vehicle_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_billing_transactions_vehicle_status', table_name='billing_transactions')
    op.drop_index('ix_billing_transactions_payment_gateway_ref', table_name='billing_transactions')
    op.drop_index('ix_billing_transactions_status', table_name='billing_transactions')
    op.drop_index('ix_billing_transactions_vehicle_id', table_name='billing_transactions')
    op.drop_index('ix_billing_transactions_toll_event_id', table_name='billing_transactions')
    op.drop_index('ix_billing_transactions_id', table_name='billing_transactions')
    op.drop_table('billing_transactions')
