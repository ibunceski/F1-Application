"""add prediction model context

Revision ID: 20260616_1000
Revises: 20260616_0900
Create Date: 2026-06-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_1000"
down_revision: Union[str, None] = "20260616_0900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("model_context", sa.String(), nullable=False, server_default="post_qualifying"),
    )
    op.add_column(
        "predictions",
        sa.Column("feature_context", sa.String(), nullable=False, server_default="post_qualifying"),
    )
    op.add_column(
        "predictions",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("UPDATE predictions SET model_context = prediction_context, feature_context = prediction_context")
    op.drop_constraint("uq_predictions_race_driver_model_context", "predictions", type_="unique")
    op.create_unique_constraint(
        "uq_predictions_race_driver_model_context",
        "predictions",
        ["race_id", "driver_id", "model_version", "model_context"],
    )
    op.alter_column("predictions", "model_context", server_default=None)
    op.alter_column("predictions", "feature_context", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_predictions_race_driver_model_context", "predictions", type_="unique")
    op.create_unique_constraint(
        "uq_predictions_race_driver_model_context",
        "predictions",
        ["race_id", "driver_id", "model_version", "prediction_context"],
    )
    op.drop_column("predictions", "generated_at")
    op.drop_column("predictions", "feature_context")
    op.drop_column("predictions", "model_context")
