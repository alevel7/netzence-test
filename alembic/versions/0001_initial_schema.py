"""Initial schema: rides, credit_lots, ledger_transactions, driver_locks

Revision ID: 0001_initial
Revises: 
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. rides
    op.create_table(
        "rides",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("driver_id", sa.String(length=100), nullable=False),
        sa.Column("distance_km", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("vehicle_type", sa.String(length=50), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="COMPLETED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rides_driver_id"), "rides", ["driver_id"], unique=False)

    # 2. credit_lots
    op.create_table(
        "credit_lots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("driver_id", sa.String(length=100), nullable=False),
        sa.Column("ride_id", sa.String(length=100), nullable=True),
        sa.Column("original_amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_lots_driver_id"), "credit_lots", ["driver_id"], unique=False)
    op.create_index(op.f("ix_credit_lots_ride_id"), "credit_lots", ["ride_id"], unique=False)
    op.create_index(op.f("ix_credit_lots_expires_at"), "credit_lots", ["expires_at"], unique=False)
    op.create_index(
        "ix_credit_lots_driver_unexpired",
        "credit_lots",
        ["driver_id", "expires_at", "earned_at"],
        unique=False,
    )

    # 3. ledger_transactions
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("driver_id", sa.String(length=100), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("ride_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ledger_transactions_driver_id"), "ledger_transactions", ["driver_id"], unique=False)
    op.create_index(op.f("ix_ledger_transactions_ride_id"), "ledger_transactions", ["ride_id"], unique=False)
    op.create_index(
        "ix_ledger_driver_created",
        "ledger_transactions",
        ["driver_id", "created_at"],
        unique=False,
    )

    # 4. driver_locks
    op.create_table(
        "driver_locks",
        sa.Column("driver_id", sa.String(length=100), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("driver_id"),
    )


def downgrade() -> None:
    op.drop_table("driver_locks")
    op.drop_index("ix_ledger_driver_created", table_name="ledger_transactions")
    op.drop_index(op.f("ix_ledger_transactions_ride_id"), table_name="ledger_transactions")
    op.drop_index(op.f("ix_ledger_transactions_driver_id"), table_name="ledger_transactions")
    op.drop_table("ledger_transactions")
    op.drop_index("ix_credit_lots_driver_unexpired", table_name="credit_lots")
    op.drop_index(op.f("ix_credit_lots_expires_at"), table_name="credit_lots")
    op.drop_index(op.f("ix_credit_lots_ride_id"), table_name="credit_lots")
    op.drop_index(op.f("ix_credit_lots_driver_id"), table_name="credit_lots")
    op.drop_table("credit_lots")
    op.drop_index(op.f("ix_rides_driver_id"), table_name="rides")
    op.drop_table("rides")
