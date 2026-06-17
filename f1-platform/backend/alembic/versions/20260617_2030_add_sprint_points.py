"""add sprint points to race results

Revision ID: 20260617_2030
Revises: 20260616_1000
Create Date: 2026-06-17 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260617_2030"
down_revision = "20260616_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "race_results",
        sa.Column("sprint_points", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("race_results", "sprint_points")
