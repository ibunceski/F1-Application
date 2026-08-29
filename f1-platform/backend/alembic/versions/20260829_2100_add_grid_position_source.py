"""add grid position source to ml features

Revision ID: 20260829_2100
Revises: 20260617_2030
Create Date: 2026-08-29 21:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_2100"
down_revision = "20260617_2030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ml_features",
        sa.Column("grid_position_source", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ml_features", "grid_position_source")
