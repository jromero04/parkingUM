"""accept occupied and used reservation projections"""

from alembic import op


revision = "20261028_metrics_usage_01"
down_revision = "20261024_metrics_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_metric_reservation_status", "reservation_projections", type_="check")
    op.create_check_constraint(
        "ck_metric_reservation_status",
        "reservation_projections",
        "status IN ('pending', 'confirmed', 'occupied', 'used', 'cancel_pending', 'cancelled', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_metric_reservation_status", "reservation_projections", type_="check")
    op.create_check_constraint(
        "ck_metric_reservation_status",
        "reservation_projections",
        "status IN ('pending', 'confirmed', 'cancel_pending', 'cancelled', 'rejected')",
    )
