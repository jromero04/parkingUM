"""create notifications tables"""
from alembic import op
import sqlalchemy as sa
revision="20261024_notifications_01"; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("reservation_states",
        sa.Column("reservation_id", sa.String(36), primary_key=True),
        sa.Column("highest_version", sa.Integer(), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("ever_confirmed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("deliveries",
        sa.Column("delivery_id", sa.String(36), primary_key=True), sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("reservation_id", sa.String(36), nullable=False),
        sa.Column("reservation_version", sa.Integer(), nullable=False), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("template", sa.String(32), nullable=False), sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("event_id", "channel", name="uq_deliveries_event_channel"),
        sa.CheckConstraint("status IN ('delivered', 'suppressed')", name="ck_deliveries_status"),
        sa.CheckConstraint("template IN ('reservation_confirmed', 'reservation_cancelled', 'request_cancelled')",
                           name="ck_deliveries_template"))
    op.create_index("ix_deliveries_reservation_version", "deliveries", ["reservation_id", "reservation_version"])
    op.create_table("processed_events", sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consumer_name", "event_id"))
def downgrade():
    op.drop_table("processed_events"); op.drop_index("ix_deliveries_reservation_version", table_name="deliveries")
    op.drop_table("deliveries"); op.drop_table("reservation_states")
