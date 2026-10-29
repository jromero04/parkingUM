"""add occupied and used reservation states"""

from alembic import op
import sqlalchemy as sa


revision = "20261028_res_usage_01"
down_revision = "20261024_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_reservations_status", "reservations", type_="check")
    op.create_check_constraint(
        "ck_reservations_status",
        "reservations",
        "status IN ('pending', 'confirmed', 'occupied', 'used', 'cancel_pending', 'cancelled', 'rejected')",
    )
    op.add_column("reservations", sa.Column("occupied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservations", sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("reservations", "used_at")
    op.drop_column("reservations", "occupied_at")
    op.drop_constraint("ck_reservations_status", "reservations", type_="check")
    op.create_check_constraint(
        "ck_reservations_status",
        "reservations",
        "status IN ('pending', 'confirmed', 'cancel_pending', 'cancelled', 'rejected')",
    )
