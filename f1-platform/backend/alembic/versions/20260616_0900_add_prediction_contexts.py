"""add prediction contexts

Revision ID: 20260616_0900
Revises: 20260614_1600
Create Date: 2026-06-16 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_0900"
down_revision: Union[str, None] = "20260614_1600"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ml_features",
        sa.Column("feature_context", sa.String(), nullable=False, server_default="post_qualifying"),
    )
    op.add_column(
        "ml_features",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "ml_features",
        sa.Column("uses_current_qualifying", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("ml_features", sa.Column("data_cutoff_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE ml_features
        SET data_cutoff_date = races.race_date
        FROM races
        WHERE races.id = ml_features.race_id
        """
    )
    op.alter_column("ml_features", "data_cutoff_date", nullable=False)

    op.drop_constraint("uq_ml_features_race_driver", "ml_features", type_="unique")
    op.create_unique_constraint(
        "uq_ml_features_race_driver_context",
        "ml_features",
        ["race_id", "driver_id", "feature_context"],
    )
    op.create_index(
        "ix_ml_features_race_driver_context",
        "ml_features",
        ["race_id", "driver_id", "feature_context"],
        unique=False,
    )
    op.create_index(
        "ix_ml_features_race_context",
        "ml_features",
        ["race_id", "feature_context"],
        unique=False,
    )

    op.add_column(
        "predictions",
        sa.Column("prediction_context", sa.String(), nullable=False, server_default="post_qualifying"),
    )
    op.drop_constraint("uq_predictions_race_driver_model_version", "predictions", type_="unique")
    op.create_unique_constraint(
        "uq_predictions_race_driver_model_context",
        "predictions",
        ["race_id", "driver_id", "model_version", "prediction_context"],
    )

    op.alter_column("ml_features", "feature_context", server_default=None)
    op.alter_column("ml_features", "uses_current_qualifying", server_default=None)
    op.alter_column("predictions", "prediction_context", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_predictions_race_driver_model_context", "predictions", type_="unique")
    op.create_unique_constraint(
        "uq_predictions_race_driver_model_version",
        "predictions",
        ["race_id", "driver_id", "model_version"],
    )
    op.drop_column("predictions", "prediction_context")

    op.drop_index("ix_ml_features_race_context", table_name="ml_features")
    op.drop_index("ix_ml_features_race_driver_context", table_name="ml_features")
    op.drop_constraint("uq_ml_features_race_driver_context", "ml_features", type_="unique")
    op.create_unique_constraint("uq_ml_features_race_driver", "ml_features", ["race_id", "driver_id"])
    op.drop_column("ml_features", "data_cutoff_date")
    op.drop_column("ml_features", "uses_current_qualifying")
    op.drop_column("ml_features", "generated_at")
    op.drop_column("ml_features", "feature_context")
