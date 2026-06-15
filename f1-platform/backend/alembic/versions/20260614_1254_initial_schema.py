"""initial_schema

Revision ID: 20260614_1254
Revises:
Create Date: 2026-06-14 12:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260614_1254"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("total_races", sa.Integer(), nullable=False),
        sa.Column("champion_driver", sa.String(), nullable=True),
        sa.Column("champion_team", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year"),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("nationality", sa.String(), nullable=True),
        sa.Column("constructor_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("constructor_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_number", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("abbreviation", sa.String(length=3), nullable=False),
        sa.Column("nationality", sa.String(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("driver_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("driver_id"),
    )
    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("circuit_name", sa.String(), nullable=False),
        sa.Column("circuit_location", sa.String(), nullable=False),
        sa.Column("circuit_country", sa.String(), nullable=False),
        sa.Column("race_name", sa.String(), nullable=False),
        sa.Column("race_date", sa.Date(), nullable=False),
        sa.Column("session_key", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("season_id", "round_number", name="uq_races_season_round"),
    )
    op.create_table(
        "lap_times",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column("lap_time_ms", sa.Float(), nullable=True),
        sa.Column("sector1_ms", sa.Float(), nullable=True),
        sa.Column("sector2_ms", sa.Float(), nullable=True),
        sa.Column("sector3_ms", sa.Float(), nullable=True),
        sa.Column("compound", sa.String(), nullable=True),
        sa.Column("tyre_age_laps", sa.Integer(), nullable=True),
        sa.Column("stint_number", sa.Integer(), nullable=True),
        sa.Column("is_pit_out_lap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_pit_in_lap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_personal_best", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("race_id", "driver_id", "lap_number", name="uq_lap_times_race_driver_lap"),
    )
    op.create_index("ix_lap_times_race_compound", "lap_times", ["race_id", "compound"], unique=False)
    op.create_table(
        "ml_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("grid_position", sa.Float(), nullable=True),
        sa.Column("qualifying_position", sa.Float(), nullable=True),
        sa.Column("gap_to_pole_ms", sa.Float(), nullable=True),
        sa.Column("avg_race_pace_ms", sa.Float(), nullable=True),
        sa.Column("driver_recent_form", sa.Float(), nullable=True),
        sa.Column("team_recent_form", sa.Float(), nullable=True),
        sa.Column("circuit_history_avg_finish", sa.Float(), nullable=True),
        sa.Column("circuit_history_dnf_rate", sa.Float(), nullable=True),
        sa.Column("dnf_rate_recent", sa.Float(), nullable=True),
        sa.Column("weather_is_wet", sa.Boolean(), nullable=False),
        sa.Column("avg_track_temp_c", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("race_id", "driver_id", name="uq_ml_features_race_driver"),
    )
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("predicted_position", sa.Float(), nullable=True),
        sa.Column("top10_probability", sa.Float(), nullable=True),
        sa.Column("podium_probability", sa.Float(), nullable=True),
        sa.Column("winner_probability", sa.Float(), nullable=True),
        sa.Column("predicted_position_gain", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("race_id", "driver_id", "model_version", name="uq_predictions_race_driver_model_version"),
    )
    op.create_table(
        "qualifying_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("q1_time_ms", sa.Float(), nullable=True),
        sa.Column("q2_time_ms", sa.Float(), nullable=True),
        sa.Column("q3_time_ms", sa.Float(), nullable=True),
        sa.Column("best_time_ms", sa.Float(), nullable=True),
        sa.Column("gap_to_pole_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("race_id", "driver_id", name="uq_qualifying_results_race_driver"),
    )
    op.create_table(
        "race_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("grid_position", sa.Integer(), nullable=True),
        sa.Column("finishing_position", sa.Integer(), nullable=True),
        sa.Column("classified_position", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("laps_completed", sa.Integer(), nullable=False),
        sa.Column("fastest_lap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fastest_lap_time_ms", sa.Float(), nullable=True),
        sa.Column("fastest_lap_rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("race_id", "driver_id", name="uq_race_results_race_driver"),
    )
    op.create_table(
        "weather_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("session_type", sa.String(), nullable=False),
        sa.Column("timestamp_offset_s", sa.Float(), nullable=False),
        sa.Column("air_temp_c", sa.Float(), nullable=True),
        sa.Column("track_temp_c", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("rainfall", sa.Boolean(), nullable=True),
        sa.Column("wind_speed_ms", sa.Float(), nullable=True),
        sa.Column("wind_direction_deg", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("weather_data")
    op.drop_table("race_results")
    op.drop_table("qualifying_results")
    op.drop_table("predictions")
    op.drop_table("ml_features")
    op.drop_index("ix_lap_times_race_compound", table_name="lap_times")
    op.drop_table("lap_times")
    op.drop_table("races")
    op.drop_table("drivers")
    op.drop_table("teams")
    op.drop_table("seasons")
