"""create parkings domain tables"""

from alembic import op
import sqlalchemy as sa


revision = "20261022_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parkings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=250), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "spots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("parking_id", sa.String(length=36), nullable=False),
        sa.Column("sensor_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("physical_occupied", sa.Boolean(), nullable=True),
        sa.Column("assigned_reservation_id", sa.String(length=36), nullable=True),
        sa.Column("sensor_status", sa.String(length=16), server_default="stale", nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=True),
        sa.Column("last_report_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sensor_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sensor_status IN ('fresh', 'stale')", name="ck_spots_sensor_status"),
        sa.ForeignKeyConstraint(["parking_id"], ["parkings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parking_id", "label", name="uq_spots_parking_label"),
        sa.UniqueConstraint("sensor_id", name="uq_spots_sensor_id"),
    )
    op.create_index("ix_spots_assigned_reservation_id", "spots", ["assigned_reservation_id"])
    op.create_index("ix_spots_parking_id_id", "spots", ["parking_id", "id"])
    op.create_table(
        "assignments",
        sa.Column("reservation_id", sa.String(length=36), nullable=False),
        sa.Column("parking_id", sa.String(length=36), nullable=True),
        sa.Column("spot_id", sa.String(length=36), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("release_operation_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('assigned', 'rejected', 'released')", name="ck_assignments_status"),
        sa.PrimaryKeyConstraint("reservation_id"),
    )
    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at", "created_at"])
    op.create_table(
        "processed_events",
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consumer_name", "event_id"),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_index("ix_outbox_unpublished", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("assignments")
    op.drop_index("ix_spots_parking_id_id", table_name="spots")
    op.drop_index("ix_spots_assigned_reservation_id", table_name="spots")
    op.drop_table("spots")
    op.drop_table("parkings")
