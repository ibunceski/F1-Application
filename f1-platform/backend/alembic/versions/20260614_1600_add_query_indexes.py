"""add query indexes

Revision ID: 20260614_1600
Revises: 20260614_1254
Create Date: 2026-06-14 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260614_1600"
down_revision: Union[str, None] = "20260614_1254"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_lap_times_compound", "lap_times", ["compound"], unique=False)
    op.create_index("ix_race_results_race_finishing_position", "race_results", ["race_id", "finishing_position"], unique=False)
    op.create_index("ix_qualifying_results_race_position", "qualifying_results", ["race_id", "position"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_qualifying_results_race_position", table_name="qualifying_results")
    op.drop_index("ix_race_results_race_finishing_position", table_name="race_results")
    op.drop_index("ix_lap_times_compound", table_name="lap_times")
