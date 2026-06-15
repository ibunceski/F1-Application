import logging
import time
from typing import Any

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import delete, select

from app.ml.model_loader import model_store
from app.models.driver import Driver
from app.models.ml_feature import MLFeature
from app.models.prediction import Prediction
from app.models.race_result import RaceResult
from app.models.team import Team
from app.schemas.prediction import PredictionResponse
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "grid_position",
    "qualifying_position",
    "gap_to_pole_ms",
    "avg_race_pace_ms",
    "driver_recent_form",
    "team_recent_form",
    "circuit_history_avg_finish",
    "circuit_history_dnf_rate",
    "dnf_rate_recent",
    "weather_is_wet",
    "avg_track_temp_c",
]


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _model_version() -> str:
    return str(model_store.model_metadata.get("trained_at") or "unknown")


class PredictionService(BaseService):
    async def get_race_features(self, race_id: int) -> pd.DataFrame:
        result = await self.db.execute(
            select(MLFeature, Driver, Team)
            .join(Driver, MLFeature.driver_id == Driver.id)
            .outerjoin(RaceResult, (RaceResult.race_id == MLFeature.race_id) & (RaceResult.driver_id == MLFeature.driver_id))
            .outerjoin(Team, Team.id == RaceResult.team_id)
            .where(MLFeature.race_id == race_id)
            .order_by(MLFeature.grid_position.asc().nulls_last())
        )
        rows = []
        for feature, driver, team in result.all():
            rows.append(
                {
                    "driver_id": driver.id,
                    "driver_name": driver.full_name,
                    "abbreviation": driver.abbreviation,
                    "driver_number": driver.driver_number,
                    "team_id": team.id if team else None,
                    "team_name": team.name if team else "Unknown",
                    "team_short_name": team.short_name if team else "Unknown",
                    "grid_position": feature.grid_position,
                    "qualifying_position": feature.qualifying_position,
                    "gap_to_pole_ms": feature.gap_to_pole_ms,
                    "avg_race_pace_ms": feature.avg_race_pace_ms,
                    "driver_recent_form": feature.driver_recent_form,
                    "team_recent_form": feature.team_recent_form,
                    "circuit_history_avg_finish": feature.circuit_history_avg_finish,
                    "circuit_history_dnf_rate": feature.circuit_history_dnf_rate,
                    "dnf_rate_recent": feature.dnf_rate_recent,
                    "weather_is_wet": feature.weather_is_wet,
                    "avg_track_temp_c": feature.avg_track_temp_c,
                }
            )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Features not computed for this race. Run feature engineering pipeline first.",
            )
        return pd.DataFrame(rows)

    async def get_existing_predictions(self, race_id: int) -> list[PredictionResponse]:
        result = await self.db.execute(
            select(Prediction, Driver, Team, MLFeature)
            .join(Driver, Prediction.driver_id == Driver.id)
            .join(MLFeature, (MLFeature.race_id == Prediction.race_id) & (MLFeature.driver_id == Prediction.driver_id))
            .outerjoin(RaceResult, (RaceResult.race_id == Prediction.race_id) & (RaceResult.driver_id == Prediction.driver_id))
            .outerjoin(Team, Team.id == RaceResult.team_id)
            .where(Prediction.race_id == race_id)
            .order_by(Prediction.predicted_position.asc().nulls_last())
        )
        return self._rows_to_responses(list(result.all()))

    def _rows_to_responses(self, rows: list[tuple[Prediction, Driver, Team | None, MLFeature]]) -> list[PredictionResponse]:
        responses: list[PredictionResponse] = []
        for rank, (prediction, driver, team, feature) in enumerate(rows, start=1):
            responses.append(
                PredictionResponse(
                    id=prediction.id,
                    driver_id=driver.id,
                    driver={
                        "id": driver.id,
                        "full_name": driver.full_name,
                        "abbreviation": driver.abbreviation,
                        "driver_number": driver.driver_number,
                    },
                    team={
                        "id": team.id if team else 0,
                        "name": team.name if team else "Unknown",
                        "short_name": team.short_name if team else "Unknown",
                    },
                    grid_position=feature.grid_position,
                    predicted_position=prediction.predicted_position,
                    predicted_rank=rank,
                    top10_probability=prediction.top10_probability,
                    podium_probability=prediction.podium_probability,
                    winner_probability=prediction.winner_probability,
                    predicted_position_gain=prediction.predicted_position_gain,
                    confidence_score=prediction.confidence_score,
                    model_version=prediction.model_version,
                )
            )
        return responses

    async def generate_predictions(self, race_id: int, force_regenerate: bool = False) -> list[PredictionResponse]:
        started_at = time.monotonic()
        try:
            if not force_regenerate:
                existing = await self.get_existing_predictions(race_id)
                if existing:
                    return existing

            if not model_store.is_ready():
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Models not loaded")

            features = await self.get_race_features(race_id)
            raw_predictions: list[dict[str, Any]] = []
            inverse_positions: list[float] = []

            for _, row in features.iterrows():
                feature_row = pd.DataFrame([row[FEATURE_COLS].to_dict()], columns=FEATURE_COLS)
                predicted_position = float(model_store.position_model.predict(feature_row)[0])
                top10_probability = float(model_store.top10_model.predict_proba(feature_row)[0][1])
                podium_probability = float(model_store.podium_model.predict_proba(feature_row)[0][1])
                predicted_gain = (
                    float(model_store.position_gain_model.predict(feature_row)[0])
                    if model_store.position_gain_model is not None
                    else None
                )
                safe_position = max(predicted_position, 0.1)
                inverse_positions.append(1.0 / safe_position)
                gap_to_pole_ms = row.get("gap_to_pole_ms")
                confidence = 0.5 if pd.isna(gap_to_pole_ms) else _clamp(1.0 - abs(float(gap_to_pole_ms)) / 2000.0)
                raw_predictions.append(
                    {
                        "race_id": race_id,
                        "driver_id": int(row["driver_id"]),
                        "model_version": _model_version(),
                        "predicted_position": round(predicted_position, 1),
                        "top10_probability": _clamp(top10_probability),
                        "podium_probability": _clamp(podium_probability),
                        "predicted_position_gain": predicted_gain,
                        "confidence_score": confidence,
                    }
                )

            inverse_total = sum(inverse_positions)
            for prediction, inverse_position in zip(raw_predictions, inverse_positions, strict=False):
                prediction["winner_probability"] = _clamp(inverse_position / inverse_total if inverse_total else 0.0)

            model_version = _model_version()
            await self.db.execute(
                delete(Prediction).where(Prediction.race_id == race_id, Prediction.model_version == model_version)
            )
            self.db.add_all([Prediction(**prediction) for prediction in raw_predictions])
            await self.db.commit()
            return await self.get_existing_predictions(race_id)
        except HTTPException:
            raise
        except Exception:
            logger.exception("Failed to generate predictions race_id=%s", race_id)
            raise
        finally:
            logger.info("Prediction generation race_id=%s took %.3fs", race_id, time.monotonic() - started_at)

    def get_feature_importances(self) -> dict[str, Any]:
        return model_store.feature_importances

    def get_model_metadata(self) -> dict[str, Any]:
        return model_store.model_metadata
