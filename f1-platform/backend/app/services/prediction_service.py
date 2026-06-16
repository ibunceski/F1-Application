import logging
import math
import time
from datetime import date, datetime, UTC
from typing import Any

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import delete, select

from app.ml.model_loader import model_store
from app.models.driver import Driver
from app.models.ml_feature import MLFeature, POST_QUALIFYING, PRE_QUALIFYING, PREDICTION_CONTEXTS
from app.models.prediction import Prediction
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.team import Team
from app.schemas.prediction import NextRacePredictionContextResponse, PredictionComparisonResponse, PredictionResponse
from app.schemas.race import RaceResponse
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

PRE_QUALIFYING_FEATURE_COLS = [
    "avg_race_pace_ms",
    "driver_recent_form",
    "team_recent_form",
    "circuit_history_avg_finish",
    "circuit_history_dnf_rate",
    "dnf_rate_recent",
    "weather_is_wet",
    "avg_track_temp_c",
]

POST_QUALIFYING_FEATURE_COLS = [
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
DEFAULT_FEATURE_COLS = {
    "pre_qualifying": PRE_QUALIFYING_FEATURE_COLS,
    "post_qualifying": POST_QUALIFYING_FEATURE_COLS,
}


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _model_version(prediction_context: str) -> str:
    metadata = model_store.metadata_for_context(prediction_context)
    return str(metadata.get("trained_at") or "unknown")


def _validate_context(prediction_context: str) -> str:
    if prediction_context not in PREDICTION_CONTEXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported prediction context: {prediction_context}",
        )
    return prediction_context


def _validate_context_request(context: str) -> str:
    if context == "auto":
        return context
    return _validate_context(context)


def _feature_columns(prediction_context: str) -> list[str]:
    return model_store.feature_columns_for_context(prediction_context) or DEFAULT_FEATURE_COLS[prediction_context]


def _prediction_rank(rows: list[tuple[Prediction, Driver, Team | None, Race, RaceResult]]) -> dict[int, int]:
    ordered = sorted(rows, key=lambda row: (row[0].predicted_position is None, row[0].predicted_position or 999.0, row[0].driver_id))
    return {prediction.driver_id: rank for rank, (prediction, *_rest) in enumerate(ordered, start=1)}


def _actual_rank(rows: list[tuple[Prediction, Driver, Team | None, Race, RaceResult]]) -> dict[int, int]:
    ordered = sorted(rows, key=lambda row: (row[4].finishing_position is None, row[4].finishing_position or 999, row[0].driver_id))
    return {prediction.driver_id: rank for rank, (prediction, *_rest) in enumerate(ordered, start=1)}


def _accuracy(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


class PredictionService(BaseService):
    async def get_next_race(self, from_date: date | None = None) -> Race:
        result = await self.db.execute(
            select(Race)
            .where(Race.race_date >= (from_date or date.today()))
            .order_by(Race.race_date.asc(), Race.round_number.asc())
            .limit(1)
        )
        race = result.scalar_one_or_none()
        if race is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No next race found")
        return race

    async def qualifying_available(self, race_id: int) -> bool:
        result = await self.db.execute(
            select(QualifyingResult.id).where(QualifyingResult.race_id == race_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def resolve_prediction_context(self, race_id: int, context: str) -> str:
        context = _validate_context_request(context)
        has_qualifying = await self.qualifying_available(race_id)
        if context == "auto":
            return POST_QUALIFYING if has_qualifying else PRE_QUALIFYING
        if context == POST_QUALIFYING and not has_qualifying:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Qualifying requested but not available for this race. Use pre_qualifying or context=auto.",
            )
        return context

    async def get_next_race_context(self) -> NextRacePredictionContextResponse:
        race = await self.get_next_race()
        has_qualifying = await self.qualifying_available(race.id)
        recommended_context = POST_QUALIFYING if has_qualifying else PRE_QUALIFYING
        return NextRacePredictionContextResponse(
            race=RaceResponse.model_validate(race),
            recommended_context=recommended_context,
            qualifying_available=has_qualifying,
            race_date=race.race_date,
            days_until_race=(race.race_date - date.today()).days,
        )

    async def get_race_features(self, race_id: int, prediction_context: str = POST_QUALIFYING) -> pd.DataFrame:
        prediction_context = _validate_context(prediction_context)
        result = await self.db.execute(
            select(MLFeature, Driver, Team)
            .join(Driver, MLFeature.driver_id == Driver.id)
            .outerjoin(Team, Team.id == Driver.team_id)
            .where(MLFeature.race_id == race_id, MLFeature.feature_context == prediction_context)
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
                    "feature_context": feature.feature_context,
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
                    "uses_current_qualifying": feature.uses_current_qualifying,
                    "data_cutoff_date": feature.data_cutoff_date,
                    "feature_generated_at": feature.generated_at,
                }
            )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Features missing for this race/context. Run "
                    f"`python ml_pipeline/feature_engineering.py --race-id {race_id} --context {prediction_context}`."
                ),
            )
        return pd.DataFrame(rows)

    async def get_existing_predictions(
        self,
        race_id: int,
        prediction_context: str = POST_QUALIFYING,
    ) -> list[PredictionResponse]:
        prediction_context = _validate_context(prediction_context)
        result = await self.db.execute(
            select(Prediction, Driver, Team, MLFeature)
            .join(Driver, Prediction.driver_id == Driver.id)
            .join(
                MLFeature,
                (MLFeature.race_id == Prediction.race_id)
                & (MLFeature.driver_id == Prediction.driver_id)
                & (MLFeature.feature_context == Prediction.feature_context),
            )
            .outerjoin(Team, Team.id == Driver.team_id)
            .where(Prediction.race_id == race_id, Prediction.model_context == prediction_context)
            .order_by(Prediction.predicted_position.asc().nulls_last())
        )
        return self._rows_to_responses(list(result.all()))

    async def _comparison_context_and_version(
        self,
        race_id: int,
        context: str,
        model_version: str | None,
    ) -> tuple[str, str]:
        if context != "latest":
            prediction_context = _validate_context(context)
            if model_version is not None:
                return prediction_context, model_version
            result = await self.db.execute(
                select(Prediction.model_version)
                .where(Prediction.race_id == race_id, Prediction.model_context == prediction_context)
                .order_by(Prediction.generated_at.desc(), Prediction.id.desc())
                .limit(1)
            )
            selected_version = result.scalar_one_or_none()
            if selected_version is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Predictions have not been generated for this race.",
                )
            return prediction_context, selected_version

        statement = select(Prediction.model_context, Prediction.model_version).where(Prediction.race_id == race_id)
        if model_version is not None:
            statement = statement.where(Prediction.model_version == model_version)
        result = await self.db.execute(statement.order_by(Prediction.generated_at.desc(), Prediction.id.desc()).limit(1))
        row = result.one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Predictions have not been generated for this race.",
            )
        return row.model_context, row.model_version

    async def get_prediction_comparison(
        self,
        race_id: int,
        context: str = "latest",
        model_version: str | None = None,
    ) -> PredictionComparisonResponse:
        result_count = await self.db.execute(select(RaceResult.id).where(RaceResult.race_id == race_id).limit(1))
        if result_count.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Race results are not available yet.")

        prediction_context, selected_version = await self._comparison_context_and_version(race_id, context, model_version)
        result = await self.db.execute(
            select(Prediction, Driver, Team, Race, RaceResult)
            .join(Driver, Prediction.driver_id == Driver.id)
            .join(Race, Prediction.race_id == Race.id)
            .join(
                RaceResult,
                (RaceResult.race_id == Prediction.race_id)
                & (RaceResult.driver_id == Prediction.driver_id),
            )
            .outerjoin(Team, Team.id == RaceResult.team_id)
            .where(
                Prediction.race_id == race_id,
                Prediction.model_context == prediction_context,
                Prediction.model_version == selected_version,
            )
        )
        rows = list(result.all())
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Predictions have not been generated for this race.",
            )

        predicted_ranks = _prediction_rank(rows)
        actual_ranks = _actual_rank(rows)
        errors: list[float] = []
        top10_hits: list[bool] = []
        podium_hits: list[bool] = []
        driver_rows: list[dict[str, Any]] = []

        for prediction, driver, team, race, race_result in sorted(
            rows,
            key=lambda row: predicted_ranks[row[0].driver_id],
        ):
            predicted_rank = predicted_ranks[prediction.driver_id]
            actual_rank = actual_ranks[prediction.driver_id]
            actual_position = race_result.finishing_position
            position_error = (
                abs(float(prediction.predicted_position) - float(actual_position))
                if prediction.predicted_position is not None and actual_position is not None
                else None
            )
            if position_error is not None:
                errors.append(position_error)

            predicted_top10 = predicted_rank <= 10
            actual_top10 = actual_position is not None and actual_position <= 10
            predicted_podium = predicted_rank <= 3
            actual_podium = actual_position is not None and actual_position <= 3
            top10_hits.append(predicted_top10 == actual_top10)
            podium_hits.append(predicted_podium == actual_podium)

            driver_rows.append(
                {
                    "driver": {
                        "id": driver.id,
                        "full_name": driver.full_name,
                        "abbreviation": driver.abbreviation,
                        "driver_number": driver.driver_number,
                    },
                    "team": {
                        "id": team.id if team else 0,
                        "name": team.name if team else "Unknown",
                        "short_name": team.short_name if team else "Unknown",
                    },
                    "predicted_position": prediction.predicted_position,
                    "predicted_rank": predicted_rank,
                    "actual_position": actual_position,
                    "actual_rank": actual_rank,
                    "position_error": position_error,
                    "predicted_top10": predicted_top10,
                    "actual_top10": actual_top10,
                    "predicted_podium": predicted_podium,
                    "actual_podium": actual_podium,
                    "points": race_result.points,
                    "status": race_result.status,
                }
            )

        mae = sum(errors) / len(errors) if errors else 0.0
        rmse = math.sqrt(sum(error * error for error in errors) / len(errors)) if errors else 0.0
        predicted_winner_driver_id = min(rows, key=lambda row: predicted_ranks[row[0].driver_id])[0].driver_id
        actual_winner_driver_id = min(rows, key=lambda row: actual_ranks[row[0].driver_id])[0].driver_id

        return PredictionComparisonResponse(
            race=RaceResponse.model_validate(rows[0][3]),
            context=prediction_context,
            model_version=selected_version,
            summary={
                "mae": mae,
                "rmse": rmse,
                "top10_accuracy": _accuracy(top10_hits),
                "podium_accuracy": _accuracy(podium_hits),
                "winner_correct": predicted_winner_driver_id == actual_winner_driver_id,
                "average_position_error": mae,
            },
            drivers=driver_rows,
        )

    def _rows_to_responses(self, rows: list[tuple[Prediction, Driver, Team | None, MLFeature]]) -> list[PredictionResponse]:
        responses: list[PredictionResponse] = []
        for rank, (prediction, driver, team, feature) in enumerate(rows, start=1):
            responses.append(
                PredictionResponse(
                    id=prediction.id,
                    driver_id=driver.id,
                    prediction_context=prediction.prediction_context,
                    model_context=prediction.model_context,
                    feature_context=prediction.feature_context,
                    generated_at=prediction.generated_at,
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
                    qualifying_position=feature.qualifying_position,
                    gap_to_pole_ms=feature.gap_to_pole_ms,
                    uses_current_qualifying=feature.uses_current_qualifying,
                    data_cutoff_date=feature.data_cutoff_date,
                    feature_generated_at=feature.generated_at,
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

    async def generate_predictions(
        self,
        race_id: int,
        force_regenerate: bool = False,
        prediction_context: str = POST_QUALIFYING,
    ) -> list[PredictionResponse]:
        prediction_context = _validate_context(prediction_context)
        started_at = time.monotonic()
        try:
            if not force_regenerate:
                existing = await self.get_existing_predictions(race_id, prediction_context)
                if existing:
                    return existing

            if not model_store.is_ready(prediction_context):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"{prediction_context} models not loaded",
                )

            features = await self.get_race_features(race_id, prediction_context)
            feature_cols = _feature_columns(prediction_context)
            models = model_store.models_for_context(prediction_context)
            raw_predictions: list[dict[str, Any]] = []
            inverse_positions: list[float] = []

            for _, row in features.iterrows():
                feature_row = pd.DataFrame([row[feature_cols].to_dict()], columns=feature_cols)
                predicted_position = float(models["position_model"].predict(feature_row)[0])
                top10_probability = float(models["top10_model"].predict_proba(feature_row)[0][1])
                podium_probability = float(models["podium_model"].predict_proba(feature_row)[0][1])
                predicted_gain = (
                    float(models["position_gain_model"].predict(feature_row)[0])
                    if models.get("position_gain_model") is not None
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
                        "prediction_context": prediction_context,
                        "model_context": prediction_context,
                        "feature_context": prediction_context,
                        "generated_at": datetime.now(UTC),
                        "model_version": _model_version(prediction_context),
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

            model_version = _model_version(prediction_context)
            await self.db.execute(
                delete(Prediction).where(
                    Prediction.race_id == race_id,
                    Prediction.model_version == model_version,
                    Prediction.model_context == prediction_context,
                )
            )
            self.db.add_all([Prediction(**prediction) for prediction in raw_predictions])
            await self.db.commit()
            return await self.get_existing_predictions(race_id, prediction_context)
        except HTTPException:
            raise
        except Exception:
            logger.exception("Failed to generate predictions race_id=%s context=%s", race_id, prediction_context)
            raise
        finally:
            logger.info(
                "Prediction generation race_id=%s context=%s took %.3fs",
                race_id,
                prediction_context,
                time.monotonic() - started_at,
            )

    def get_feature_importances(self) -> dict[str, Any]:
        return model_store.feature_importances_by_context

    def get_model_metadata(self) -> dict[str, Any]:
        return model_store.model_metadata_by_context

    async def generate_next_race_predictions(
        self,
        context: str = "auto",
        force_regenerate: bool = False,
    ) -> list[PredictionResponse]:
        race = await self.get_next_race()
        prediction_context = await self.resolve_prediction_context(race.id, context)
        return await self.generate_predictions(race.id, force_regenerate, prediction_context)

    async def get_next_race_predictions(self, context: str = "auto") -> list[PredictionResponse]:
        race = await self.get_next_race()
        prediction_context = await self.resolve_prediction_context(race.id, context)
        predictions = await self.get_existing_predictions(race.id, prediction_context)
        if not predictions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No predictions have been generated for the next race",
            )
        return predictions
