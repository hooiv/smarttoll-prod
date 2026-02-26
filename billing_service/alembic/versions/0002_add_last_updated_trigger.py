"""Add last_updated trigger for billing_transactions

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-25

Ensures the last_updated column is always refreshed to the current timestamp
whenever a billing_transactions row is updated, regardless of whether the
update was made via the ORM, raw SQL, or any other client.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the trigger function (idempotent)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_billing_transactions_last_updated()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.last_updated = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create the trigger, but only if it does not already exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_billing_transactions_last_updated'
                  AND tgrelid = 'billing_transactions'::regclass
            ) THEN
                CREATE TRIGGER trg_billing_transactions_last_updated
                BEFORE UPDATE ON billing_transactions
                FOR EACH ROW
                EXECUTE FUNCTION update_billing_transactions_last_updated();
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER IF EXISTS trg_billing_transactions_last_updated
        ON billing_transactions;
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS update_billing_transactions_last_updated();
    """)
