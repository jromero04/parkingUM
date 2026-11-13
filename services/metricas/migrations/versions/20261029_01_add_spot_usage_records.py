"""add historical spot usage records"""

from alembic import op
import sqlalchemy as sa


revision = "20261029_metrics_usage_01"
down_revision = "20261028_metrics_usage_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spot_usage_records",
        sa.Column("reservation_id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("parking_id", sa.String(36), nullable=False),
        sa.Column("spot_id", sa.String(36), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_spot_usage_parking_used", "spot_usage_records", ["parking_id", "used_at"])
    op.create_index("ix_spot_usage_spot_used", "spot_usage_records", ["spot_id", "used_at"])
    op.execute("""
        INSERT INTO spot_usage_records
            (reservation_id, event_id, parking_id, spot_id, used_at, projected_at)
        SELECT id, id, parking_id, spot_id, source_updated_at, projected_at
        FROM reservation_projections
        WHERE status = 'used'
        ON CONFLICT (reservation_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_spot_usage_spot_used", table_name="spot_usage_records")
    op.drop_index("ix_spot_usage_parking_used", table_name="spot_usage_records")
    op.drop_table("spot_usage_records")
