"""create metrics projections"""

from alembic import op
import sqlalchemy as sa


revision = "20261024_metrics_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spot_projections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parking_id", sa.String(36), nullable=False),
        sa.Column("sensor_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("physical_occupied", sa.Boolean(), nullable=True),
        sa.Column("assigned_reservation_id", sa.String(36), nullable=True),
        sa.Column("sensor_status", sa.String(16), nullable=False),
        sa.Column("last_report_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sensor_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sensor_status IN ('fresh', 'stale')", name="ck_metric_spot_sensor_status"),
        sa.CheckConstraint("availability IN ('available', 'reserved', 'occupied', 'unknown')",
                           name="ck_metric_spot_availability"),
    )
    op.create_index("ix_metric_spots_parking_id", "spot_projections", ["parking_id", "id"])
    op.create_table(
        "reservation_projections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("parking_id", sa.String(36), nullable=False),
        sa.Column("spot_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("ever_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'cancel_pending', 'cancelled', 'rejected')",
                           name="ck_metric_reservation_status"),
    )
    op.create_index("ix_metric_reservations_parking_id", "reservation_projections", ["parking_id", "id"])
    op.create_table(
        "processed_events",
        sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consumer_name", "event_id"),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_index("ix_metric_reservations_parking_id", table_name="reservation_projections")
    op.drop_table("reservation_projections")
    op.drop_index("ix_metric_spots_parking_id", table_name="spot_projections")
    op.drop_table("spot_projections")
