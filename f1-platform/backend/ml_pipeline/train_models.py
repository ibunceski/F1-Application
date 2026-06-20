"""Reproducible, leakage-safe F1 model experiment runner.

The runner deliberately separates development-season model selection from the
final completed-season evaluation.  It writes a self-contained experiment
directory before promoting only the selected models to the filenames consumed
by ``app.ml.model_loader``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable, Literal

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from lightgbm import LGBMClassifier, LGBMRegressor
from sqlalchemy import text
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.models.ml_feature import POST_QUALIFYING, PRE_QUALIFYING
from ingestion.db_helpers import get_sync_engine

LOGGER = logging.getLogger("ml.experiments")

# Weather columns exist in MLFeature but are intentionally excluded until their
# target-race provenance is bounded by the prediction cutoff (see the design).
PRE_QUALIFYING_FEATURE_COLS = [
    "avg_race_pace_ms",
    "driver_recent_form",
    "team_recent_form",
    "circuit_history_avg_finish",
    "circuit_history_dnf_rate",
    "dnf_rate_recent",
]
POST_QUALIFYING_FEATURE_COLS = [
    "grid_position",
    "qualifying_position",
    "gap_to_pole_ms",
    *PRE_QUALIFYING_FEATURE_COLS,
]
CONTEXT_FEATURE_COLS = {
    PRE_QUALIFYING: PRE_QUALIFYING_FEATURE_COLS,
    POST_QUALIFYING: POST_QUALIFYING_FEATURE_COLS,
}

TARGET_POSITION = "actual_finishing_position"
TARGET_TOP10 = "finished_top10"
TARGET_PODIUM = "finished_podium"
TARGET_GAIN = "position_gain_loss"
TaskName = Literal["position_model", "top10_model", "podium_model", "position_gain_model"]
TASK_TARGETS: dict[TaskName, str] = {
    "position_model": TARGET_POSITION,
    "top10_model": TARGET_TOP10,
    "podium_model": TARGET_PODIUM,
    "position_gain_model": TARGET_GAIN,
}
TASK_KINDS: dict[TaskName, Literal["regression", "classification"]] = {
    "position_model": "regression",
    "top10_model": "classification",
    "podium_model": "classification",
    "position_gain_model": "regression",
}
MODEL_FILENAMES: dict[TaskName, str] = {
    "position_model": "position_model.joblib",
    "top10_model": "top10_model.joblib",
    "podium_model": "podium_model.joblib",
    "position_gain_model": "position_gain_model.joblib",
}
PRIMARY_METRIC = {
    "position_model": "mae",
    "position_gain_model": "mae",
    "top10_model": "roc_auc",
    "podium_model": "pr_auc",
}
LOWER_IS_BETTER = {"mae", "rmse", "brier", "log_loss"}
METRIC_COLUMNS = {
    "mae", "rmse", "r2", "spearman", "mean_race_spearman", "within_2_positions_accuracy", "sign_accuracy",
    "accuracy", "balanced_accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "brier", "log_loss",
}


@dataclass(frozen=True)
class TemporalFold:
    name: str
    train_seasons: tuple[int, ...]
    validation_season: int


@dataclass(frozen=True)
class Candidate:
    name: str
    complexity: int
    factory: Callable[[pd.Series, int], Any]


class MedianRegressor(BaseEstimator, RegressorMixin):
    """Historical/no-skill median baseline, learned on the fold only."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "MedianRegressor":
        self.value_ = float(pd.Series(y).median())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.value_, dtype=float)


class ZeroChangeRegressor(BaseEstimator, RegressorMixin):
    """Position gain/loss baseline: predict no net position change."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ZeroChangeRegressor":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(X), dtype=float)


class GridPositionRegressor(BaseEstimator, RegressorMixin):
    """Operational post-qualifying baseline using only the known starting grid."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "GridPositionRegressor":
        self.fallback_ = float(pd.Series(y).median())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        values = pd.to_numeric(X["grid_position"], errors="coerce").fillna(self.fallback_)
        return values.to_numpy(dtype=float)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reproducible F1 temporal ML experiments.")
    parser.add_argument("--train-seasons", nargs="+", type=int, required=True, help="Completed development seasons.")
    parser.add_argument(
        "--evaluation-seasons",
        nargs="+",
        type=int,
        help="Exactly one final completed holdout season. It must be later than all training seasons.",
    )
    # Compatibility with the original trainer command; the value is treated as
    # the single final evaluation season and is never used for selection.
    parser.add_argument("--test-season", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--context",
        "--contexts",
        dest="context",
        nargs="+",
        choices=[PRE_QUALIFYING, POST_QUALIFYING, "all"],
        default=["all"],
    )
    parser.add_argument("--experiment-id", help="Immutable experiment directory name. Defaults to a timestamped ID.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-train-seasons", type=int, default=3)
    parser.add_argument("--artifact-output-dir", default="models_store", help="Directory containing experiments/.")
    parser.add_argument(
        "--model-output-dir",
        "--deployment-output-dir",
        dest="deployment_output_dir",
        default="models_store",
        help="Directory consumed by FastAPI ModelStore; existing model filenames are promoted here.",
    )
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date.today(), help="Snapshot date for completion validation (YYYY-MM-DD).")
    parser.add_argument("--generate-plots", action="store_true", help="Create headless thesis figures from saved CSV artifacts.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout), logging.FileHandler(logs_dir / "train_models.log")]
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=handlers, force=True)


def resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path


def normalise_contexts(requested: list[str]) -> list[str]:
    if "all" in requested:
        return [PRE_QUALIFYING, POST_QUALIFYING]
    return sorted(set(requested))


def validate_season_arguments(train_seasons: list[int], evaluation_seasons: list[int], min_train_seasons: int) -> None:
    if len(set(train_seasons)) != len(train_seasons):
        raise ValueError("--train-seasons contains duplicate years.")
    if len(evaluation_seasons) != 1:
        raise ValueError("Exactly one --evaluation-seasons year is required for a final held-out evaluation.")
    if len(train_seasons) < min_train_seasons + 1:
        raise ValueError("At least min-train-seasons + 1 development seasons are required for rolling validation.")
    if set(train_seasons) & set(evaluation_seasons):
        raise ValueError("Training and evaluation seasons must be disjoint.")
    if max(train_seasons) >= min(evaluation_seasons):
        raise ValueError("Every development season must strictly precede the final evaluation season.")


def generate_temporal_folds(seasons: list[int], min_train_seasons: int = 3) -> list[TemporalFold]:
    """Return expanding, season-level folds with no contemporaneous leakage."""
    ordered = sorted(set(seasons))
    if len(ordered) != len(seasons):
        raise ValueError("Temporal folds require unique seasons.")
    if len(ordered) <= min_train_seasons:
        raise ValueError("Insufficient seasons for an expanding temporal validation fold.")
    return [
        TemporalFold(
            name=f"fold_{index - min_train_seasons + 1}_{season}",
            train_seasons=tuple(ordered[:index]),
            validation_season=season,
        )
        for index, season in enumerate(ordered)
        if index >= min_train_seasons
    ]


def assert_no_future_data(train_df: pd.DataFrame, validation_df: pd.DataFrame) -> None:
    """Defensive runtime check used for every fold before fitting."""
    if train_df.empty or validation_df.empty:
        raise ValueError("Temporal split has an empty training or validation partition.")
    if int(train_df["season_year"].max()) >= int(validation_df["season_year"].min()):
        raise ValueError("Temporal leakage: a training season is not earlier than validation.")
    if "race_date" in train_df and "race_date" in validation_df:
        if pd.to_datetime(train_df["race_date"]).max() >= pd.to_datetime(validation_df["race_date"]).min():
            raise ValueError("Temporal leakage: a training race is not earlier than validation.")


def validate_completed_seasons(seasons: list[int], context: str, as_of: date) -> list[dict[str, Any]]:
    """Fail closed when a requested season is not fully ingested and completed.

    This deliberately checks the database schedule, race results, and (where
    needed) qualifying results before any training data are loaded.
    """
    query_template = """
        SELECT
            s.year, s.total_races, r.id AS race_id, r.round_number, r.race_date,
            (SELECT COUNT(*) FROM race_results rr WHERE rr.race_id = r.id) AS result_rows,
            (SELECT COUNT(*) FROM qualifying_results qr WHERE qr.race_id = r.id) AS qualifying_rows,
            (SELECT COUNT(*) FROM race_results rr
             WHERE rr.race_id = r.id AND rr.status IS NOT NULL AND rr.laps_completed >= 0) AS valid_result_rows
        FROM seasons s
        LEFT JOIN races r ON r.season_id = s.id
        WHERE s.year IN ({years})
        ORDER BY s.year, r.round_number
        """
    # The requested years are validated integers, so interpolating the compact
    # integer list avoids driver-specific array expansion semantics.
    placeholders = ", ".join(str(int(year)) for year in sorted(set(seasons)))
    query = text(query_template.format(years=placeholders))
    rows = pd.read_sql_query(query, get_sync_engine())
    reports: list[dict[str, Any]] = []
    for year in sorted(set(seasons)):
        season_rows = rows[rows["year"] == year].copy()
        if season_rows.empty:
            raise ValueError(f"Season {year} is missing from the database.")
        total_races = int(season_rows["total_races"].iloc[0])
        rounds = sorted(season_rows["round_number"].dropna().astype(int).tolist())
        failures: list[str] = []
        if len(season_rows) != total_races or rounds != list(range(1, total_races + 1)):
            failures.append("schedule does not contain every expected round exactly once")
        if season_rows["race_date"].isna().any() or any(pd.to_datetime(season_rows["race_date"]).dt.date >= as_of):
            failures.append("contains a race on or after the snapshot date")
        if (season_rows["result_rows"] < 10).any() or (season_rows["valid_result_rows"] < 10).any():
            failures.append("one or more races has an implausibly incomplete result set")
        if context == POST_QUALIFYING and (season_rows["qualifying_rows"] < 10).any():
            failures.append("one or more races has an implausibly incomplete qualifying set")
        report = {
            "year": year,
            "total_races": total_races,
            "stored_races": int(len(season_rows)),
            "minimum_result_rows": int(season_rows["result_rows"].min()),
            "minimum_qualifying_rows": int(season_rows["qualifying_rows"].min()),
            "max_race_date": str(pd.to_datetime(season_rows["race_date"]).max().date()),
            "valid": not failures,
            "failures": failures,
        }
        reports.append(report)
        if failures:
            raise ValueError(f"Season {year} is not complete for {context}: {'; '.join(failures)}")
    return reports


def load_feature_dataframe(feature_context: str, allowed_seasons: list[int]) -> pd.DataFrame:
    query = text(
        """
        SELECT
            mf.race_id, mf.driver_id, mf.feature_context, s.year AS season_year, r.race_date,
            mf.grid_position, mf.qualifying_position, mf.gap_to_pole_ms,
            mf.avg_race_pace_ms, mf.driver_recent_form, mf.team_recent_form,
            mf.circuit_history_avg_finish, mf.circuit_history_dnf_rate, mf.dnf_rate_recent,
            mf.weather_is_wet, mf.avg_track_temp_c, mf.data_cutoff_date,
            rr.finishing_position AS actual_finishing_position,
            CASE WHEN rr.race_id IS NULL THEN NULL WHEN rr.finishing_position <= 10 THEN TRUE ELSE FALSE END AS finished_top10,
            CASE WHEN rr.race_id IS NULL THEN NULL WHEN rr.finishing_position <= 3 THEN TRUE ELSE FALSE END AS finished_podium,
            CASE WHEN rr.grid_position IS NULL OR rr.finishing_position IS NULL THEN NULL
                 ELSE rr.grid_position - rr.finishing_position END AS position_gain_loss
        FROM ml_features mf
        JOIN races r ON r.id = mf.race_id
        JOIN seasons s ON s.id = r.season_id
        LEFT JOIN race_results rr ON rr.race_id = mf.race_id AND rr.driver_id = mf.driver_id
        WHERE mf.feature_context = :feature_context
        """
    )
    df = pd.read_sql_query(query, get_sync_engine(), params={"feature_context": feature_context})
    df = df[df["season_year"].isin(allowed_seasons)].copy()
    if df.empty:
        raise ValueError(f"No {feature_context} feature rows found for requested seasons.")
    # Historical post-qualifying candidates must be eligible for the same
    # fields used by their context.  Missing values in other columns remain a
    # fold-local imputation concern.
    if feature_context == POST_QUALIFYING:
        df = df[df["grid_position"].notna() & df["qualifying_position"].notna()].copy()
    return df.sort_values(["season_year", "race_date", "race_id", "driver_id"]).reset_index(drop=True)


def build_preprocessor(feature_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), feature_cols)],
        remainder="drop",
    )


def build_pipeline(estimator: Any, feature_cols: list[str]) -> Pipeline:
    return Pipeline([("preprocessor", build_preprocessor(feature_cols)), ("model", estimator)])


def _class_weight_scale(y: pd.Series) -> float:
    positives = int((y.astype(int) == 1).sum())
    negatives = int((y.astype(int) == 0).sum())
    return float(negatives / positives) if positives else 1.0


def candidate_factories(task: TaskName, context: str, feature_cols: list[str]) -> list[Candidate]:
    """Return one fixed, seeded configuration per requested algorithm family."""
    kind = TASK_KINDS[task]
    if kind == "regression":
        candidates = [
            Candidate("MedianBaseline", 0, lambda _y, _seed: MedianRegressor()),
        ]
        if task == "position_gain_model":
            candidates[0] = Candidate("ZeroChangeBaseline", 0, lambda _y, _seed: ZeroChangeRegressor())
        if task == "position_model" and context == POST_QUALIFYING and "grid_position" in feature_cols:
            candidates.append(Candidate("GridPositionBaseline", 0, lambda _y, _seed: GridPositionRegressor()))
        candidates.extend(
            [
                Candidate("Ridge", 1, lambda _y, _seed: build_pipeline(Ridge(alpha=1.0), feature_cols)),
                Candidate("ElasticNet", 2, lambda _y, _seed: build_pipeline(ElasticNet(alpha=0.05, l1_ratio=0.5, max_iter=10000), feature_cols)),
                Candidate("RandomForestRegressor", 3, lambda _y, seed: build_pipeline(RandomForestRegressor(n_estimators=300, max_depth=10, min_samples_leaf=2, random_state=seed, n_jobs=1), feature_cols)),
                Candidate("XGBRegressor", 4, lambda _y, seed: build_pipeline(XGBRegressor(n_estimators=250, max_depth=5, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, random_state=seed, n_jobs=1), feature_cols)),
                Candidate("LGBMRegressor", 4, lambda _y, seed: build_pipeline(LGBMRegressor(n_estimators=250, max_depth=6, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, random_state=seed, n_jobs=1, verbose=-1), feature_cols)),
            ]
        )
        return candidates
    return [
        Candidate("PrevalenceBaseline", 0, lambda _y, _seed: build_pipeline(DummyClassifier(strategy="prior", random_state=0), feature_cols)),
        Candidate("LogisticRegression", 1, lambda _y, seed: build_pipeline(LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced", random_state=seed), feature_cols)),
        Candidate("RandomForestClassifier", 3, lambda _y, seed: build_pipeline(RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=2, class_weight="balanced", random_state=seed, n_jobs=1), feature_cols)),
        Candidate("XGBClassifier", 4, lambda y, seed: build_pipeline(XGBClassifier(n_estimators=250, max_depth=5, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, scale_pos_weight=_class_weight_scale(y), random_state=seed, n_jobs=1, eval_metric="logloss"), feature_cols)),
        Candidate("LGBMClassifier", 4, lambda y, seed: build_pipeline(LGBMClassifier(n_estimators=250, max_depth=6, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, class_weight="balanced", random_state=seed, n_jobs=1, verbose=-1), feature_cols)),
    ]


def feature_ablation_sets(context: str) -> dict[str, list[str]]:
    """Feature subsets used to quantify information-set contribution.

    The post-qualifying ``all_features`` condition deliberately includes the
    grid/qualifying fields; this makes the information gain explicit while
    retaining the exact same target semantics and temporal splits.
    """
    form_only = ["driver_recent_form", "team_recent_form"]
    form_plus_circuit = [*form_only, "circuit_history_avg_finish", "circuit_history_dnf_rate"]
    sets = {
        "form_only": form_only,
        "form_plus_circuit_history": form_plus_circuit,
    }
    all_features_name = "all_features_including_grid_qualifying" if context == POST_QUALIFYING else "all_features"
    sets[all_features_name] = list(CONTEXT_FEATURE_COLS[context])
    return sets


def mean_per_race_spearman(y_true: pd.Series, predictions: np.ndarray, race_ids: pd.Series) -> float:
    """Mean of valid within-race Spearman correlations, not a pooled proxy."""
    frame = pd.DataFrame({"actual": y_true.to_numpy(), "prediction": np.asarray(predictions), "race_id": race_ids.to_numpy()})
    correlations = [
        group["actual"].corr(group["prediction"], method="spearman")
        for _, group in frame.groupby("race_id", sort=False)
        if len(group) > 1
    ]
    valid = [float(value) for value in correlations if pd.notna(value)]
    return float(np.mean(valid)) if valid else float("nan")


def regression_metrics(y_true: pd.Series, predictions: np.ndarray, task: TaskName, race_ids: pd.Series | None = None) -> dict[str, float]:
    y = np.asarray(y_true, dtype=float)
    pred = np.asarray(predictions, dtype=float)
    metrics = {
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "r2": float(r2_score(y, pred)) if len(y) > 1 else float("nan"),
        "spearman": float(pd.Series(y).corr(pd.Series(pred), method="spearman")) if len(y) > 1 else float("nan"),
    }
    if task == "position_model":
        metrics["within_2_positions_accuracy"] = float(np.mean(np.abs(y - pred) <= 2.0))
        metrics["mean_race_spearman"] = mean_per_race_spearman(y_true, pred, race_ids) if race_ids is not None else float("nan")
    if task == "position_gain_model":
        metrics["sign_accuracy"] = float(np.mean(np.sign(y) == np.sign(pred)))
    return metrics


def classification_metrics(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, float]:
    y = np.asarray(y_true, dtype=int)
    proba = np.clip(np.asarray(probabilities, dtype=float), 1e-7, 1 - 1e-7)
    predicted = (proba >= threshold).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y, predicted)),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "brier": float(brier_score_loss(y, proba)),
        "log_loss": float(log_loss(y, proba, labels=[0, 1])),
    }
    metrics["roc_auc"] = float(roc_auc_score(y, proba)) if len(np.unique(y)) == 2 else float("nan")
    metrics["pr_auc"] = float(average_precision_score(y, proba)) if len(np.unique(y)) == 2 else float("nan")
    return metrics


def calibration_reliability(y_true: pd.Series, probabilities: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Return deterministic reliability-bin data for thesis plots and tables."""
    if n_bins < 2:
        raise ValueError("Calibration requires at least two bins.")
    y = np.asarray(y_true, dtype=int)
    proba = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.minimum(np.digitize(proba, edges[1:-1], right=False), n_bins - 1)
    rows: list[dict[str, Any]] = []
    for index in range(n_bins):
        mask = indices == index
        count = int(mask.sum())
        rows.append(
            {
                "bin": index,
                "bin_lower": float(edges[index]),
                "bin_upper": float(edges[index + 1]),
                "count": count,
                "mean_predicted_probability": float(proba[mask].mean()) if count else float("nan"),
                "observed_positive_rate": float(y[mask].mean()) if count else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def choose_classification_threshold(candidate: Candidate, train_df: pd.DataFrame, target: str, feature_cols: list[str], seed: int) -> tuple[float, int | None]:
    """Choose a threshold on a strictly earlier inner season, never outer data."""
    inner_seasons = sorted(train_df["season_year"].unique().tolist())
    if len(inner_seasons) < 2:
        return 0.5, None
    threshold_season = inner_seasons[-1]
    inner_train = train_df[train_df["season_year"] < threshold_season]
    inner_validation = train_df[train_df["season_year"] == threshold_season]
    if inner_train.empty or inner_validation.empty or inner_train[target].nunique() < 2:
        return 0.5, None
    model = candidate.factory(inner_train[target].astype(int), seed)
    model.fit(inner_train[feature_cols], inner_train[target].astype(int))
    probabilities = model.predict_proba(inner_validation[feature_cols])[:, 1]
    thresholds = np.linspace(0.05, 0.95, 19)
    scores = [f1_score(inner_validation[target].astype(int), probabilities >= threshold, zero_division=0) for threshold in thresholds]
    best_score = max(scores)
    # The first maximum is the lower threshold, as specified in the design.
    return float(thresholds[scores.index(best_score)]), int(threshold_season)


def evaluate_candidate(
    candidate: Candidate,
    task: TaskName,
    context: str,
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    feature_cols: list[str],
    fold_name: str,
    seed: int,
    phase: str,
    analysis_type: str = "candidate_model",
    ablation: str | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, Any]:
    target = TASK_TARGETS[task]
    train_target = train_df[train_df[target].notna()].copy()
    validation_target = validation_df[validation_df[target].notna()].copy()
    assert_no_future_data(train_target, validation_target)
    if train_target.empty or validation_target.empty:
        raise ValueError(f"No eligible rows for {task} in {fold_name}.")
    kind = TASK_KINDS[task]
    threshold = 0.5
    threshold_selection_season: int | None = None
    if kind == "classification":
        if train_target[target].nunique() < 2:
            raise ValueError(f"Training partition has one class for {task} in {fold_name}.")
        threshold, threshold_selection_season = choose_classification_threshold(candidate, train_target, target, feature_cols, seed)
        y_train = train_target[target].astype(int)
    else:
        y_train = train_target[target].astype(float)
    model = candidate.factory(y_train, seed)
    model.fit(train_target[feature_cols], y_train)
    if kind == "classification":
        probabilities = model.predict_proba(validation_target[feature_cols])[:, 1]
        metrics = classification_metrics(validation_target[target].astype(int), probabilities, threshold)
        predictions = (probabilities >= threshold).astype(int)
        row_prediction = probabilities
    else:
        predictions = np.asarray(model.predict(validation_target[feature_cols]), dtype=float)
        probabilities = np.full(len(predictions), np.nan)
        metrics = regression_metrics(validation_target[target].astype(float), predictions, task, validation_target["race_id"])
        row_prediction = predictions
    result = {
        "phase": phase,
        "fold": fold_name,
        "context": context,
        "task": task,
        "algorithm": candidate.name,
        "analysis_type": analysis_type,
        "ablation": ablation,
        "evaluation_season": int(validation_target["season_year"].iloc[0]),
        "threshold": threshold if kind == "classification" else np.nan,
        "threshold_selection_season": threshold_selection_season,
        "threshold_selection_scope": "inner_validation_before_outer" if kind == "classification" else None,
        "train_rows": len(train_target),
        "validation_rows": len(validation_target),
        **metrics,
    }
    predictions_df = pd.DataFrame(
        {
            "phase": phase,
            "fold": fold_name,
            "context": context,
            "task": task,
            "algorithm": candidate.name,
            "analysis_type": analysis_type,
            "ablation": ablation,
            "race_id": validation_target["race_id"].to_numpy(),
            "driver_id": validation_target["driver_id"].to_numpy(),
            "season_year": validation_target["season_year"].to_numpy(),
            "actual": validation_target[target].to_numpy(),
            "prediction": row_prediction,
            "probability": probabilities,
            "threshold": threshold if kind == "classification" else np.nan,
            "threshold_selection_season": threshold_selection_season,
            "threshold_selection_scope": "inner_validation_before_outer" if kind == "classification" else None,
        }
    )
    return result, predictions_df, model


def aggregate_validation_results(results: pd.DataFrame, candidates: dict[tuple[str, TaskName], list[Candidate]]) -> pd.DataFrame:
    validation = results[results["phase"] == "validation"].copy()
    metric_columns = [column for column in validation.columns if column in METRIC_COLUMNS]
    grouped = validation.groupby(["context", "task", "algorithm"], dropna=False)
    aggregate = grouped[metric_columns].agg(["mean", "std"])
    aggregate.columns = [f"{metric}_{stat}" for metric, stat in aggregate.columns]
    aggregate["fold_count"] = grouped.size()
    aggregate = aggregate.reset_index()
    aggregate["primary_metric"] = aggregate["task"].map(PRIMARY_METRIC)
    aggregate["primary_score"] = [row[f"{row['primary_metric']}_mean"] for _, row in aggregate.iterrows()]
    aggregate["rank"] = np.nan
    aggregate["champion"] = False
    for (context, task), group in aggregate.groupby(["context", "task"], sort=False):
        primary = PRIMARY_METRIC[task]
        ascending = primary in LOWER_IS_BETTER
        candidate_order = {candidate.name: candidate.complexity for candidate in candidates[(context, task)]}
        eligible = group[np.isfinite(group["primary_score"].astype(float))].copy()
        if eligible.empty:
            raise RuntimeError(f"No valid validation result for {context}/{task}.")
        eligible["complexity"] = eligible["algorithm"].map(candidate_order)
        eligible = eligible.sort_values(["primary_score", "complexity", "algorithm"], ascending=[ascending, True, True])
        aggregate.loc[eligible.index, "rank"] = range(1, len(eligible) + 1)
        aggregate.loc[eligible.index[0], "champion"] = True
    return aggregate.sort_values(["context", "task", "rank", "algorithm"]).reset_index(drop=True)


def aggregate_ablation_results(results: pd.DataFrame) -> pd.DataFrame:
    """Aggregate feature subsets, selecting models only with validation folds."""
    validation = results[results["phase"] == "validation"].copy()
    metric_columns = [column for column in validation.columns if column in METRIC_COLUMNS]
    grouped = validation.groupby(["context", "task", "ablation", "algorithm"], dropna=False)
    aggregate = grouped[metric_columns].agg(["mean", "std"])
    aggregate.columns = [f"{metric}_{stat}" for metric, stat in aggregate.columns]
    aggregate["fold_count"] = grouped.size()
    aggregate = aggregate.reset_index()
    aggregate["analysis_type"] = "feature_ablation"
    aggregate["primary_metric"] = aggregate["task"].map(PRIMARY_METRIC)
    aggregate["primary_score"] = [row[f"{row['primary_metric']}_mean"] for _, row in aggregate.iterrows()]
    aggregate["rank"] = np.nan
    aggregate["ablation_champion"] = False
    aggregate["best_ablation"] = False
    for (_, task, _), group in aggregate.groupby(["context", "task", "ablation"], sort=False):
        primary = PRIMARY_METRIC[task]
        eligible = group[np.isfinite(group["primary_score"].astype(float))].sort_values("primary_score", ascending=primary in LOWER_IS_BETTER)
        aggregate.loc[eligible.index, "rank"] = range(1, len(eligible) + 1)
        if not eligible.empty:
            aggregate.loc[eligible.index[0], "ablation_champion"] = True
    for (_, task), group in aggregate[aggregate["ablation_champion"]].groupby(["context", "task"], sort=False):
        primary = PRIMARY_METRIC[task]
        best = group.sort_values("primary_score", ascending=primary in LOWER_IS_BETTER)
        if not best.empty:
            aggregate.loc[best.index[0], "best_ablation"] = True
    return aggregate.sort_values(["context", "task", "rank", "ablation"]).reset_index(drop=True)


def data_fingerprint(df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    columns = ["race_id", "driver_id", "season_year", "race_date", "data_cutoff_date", *feature_cols, *TASK_TARGETS.values()]
    existing = [column for column in columns if column in df.columns]
    canonical = df[existing].sort_values(["season_year", "race_date", "race_id", "driver_id"]).to_csv(index=False, na_rep="<NA>")
    return {
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "rows": int(len(df)),
        "columns": existing,
        "season_counts": {str(year): int(count) for year, count in df.groupby("season_year").size().items()},
    }


def package_versions() -> dict[str, str]:
    names = ["numpy", "pandas", "scikit-learn", "xgboost", "lightgbm", "matplotlib", "joblib", "sqlalchemy"]
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(json_safe(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def feature_importances(model: Any, feature_cols: list[str]) -> dict[str, float]:
    estimator = model
    if isinstance(model, Pipeline):
        estimator = model.named_steps["model"]
    values = getattr(estimator, "feature_importances_", None)
    if values is None and hasattr(estimator, "coef_"):
        values = np.abs(np.asarray(estimator.coef_)).ravel()
    if values is None:
        return {}
    return {name: float(value) for name, value in zip(feature_cols, values, strict=False)}


def write_markdown_report(path: Path, manifest: dict[str, Any], aggregate: pd.DataFrame, final_results: pd.DataFrame) -> None:
    lines = [
        "# F1 ML Experiment Report",
        "",
        f"- Experiment ID: `{manifest['experiment_id']}`",
        f"- Completed at: `{manifest['completed_at']}`",
        f"- Development seasons: `{manifest['train_seasons']}`",
        f"- Final held-out season: `{manifest['evaluation_season']}`",
        f"- Seed: `{manifest['seed']}`",
        "",
        "## Rolling-origin validation champions",
        "",
        "| Context | Task | Champion | Primary metric | Mean validation score | Std. dev. |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    champions = aggregate[aggregate["champion"]]
    for _, row in champions.iterrows():
        metric = row["primary_metric"]
        lines.append(f"| {row['context']} | {row['task']} | {row['algorithm']} | {metric} | {row['primary_score']:.4f} | {row.get(f'{metric}_std', np.nan):.4f} |")
    lines.extend(["", "## Final completed-season evaluation", "", "| Context | Task | Algorithm | Primary metric | Score |", "| --- | --- | --- | --- | ---: |"])
    for _, row in final_results.iterrows():
        metric = PRIMARY_METRIC[row["task"]]
        lines.append(f"| {row['context']} | {row['task']} | {row['algorithm']} | {metric} | {row[metric]:.4f} |")
    lines.extend(
        [
            "",
            "## Reproducibility notes",
            "",
            "This report was generated using only completed seasons that passed the database completeness gate. "
            "Weather fields were excluded because their current target-race provenance is not bounded by the prediction cutoff. "
            "The final held-out season was not used for model family selection or classification-threshold selection.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_calibration_artifacts(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Persist probability rows and reliability bins without touching models."""
    columns = ["phase", "fold", "context", "task", "algorithm", "analysis_type", "ablation", "race_id", "driver_id", "actual", "probability", "threshold"]
    calibration = predictions[predictions["task"].isin(["top10_model", "podium_model"])][columns].copy()
    bin_columns = ["phase", "fold", "context", "task", "algorithm", "analysis_type", "ablation", "bin", "bin_lower", "bin_upper", "count", "mean_predicted_probability", "observed_positive_rate"]
    if calibration.empty:
        return calibration, pd.DataFrame(columns=bin_columns)
    group_columns = ["phase", "fold", "context", "task", "algorithm", "analysis_type", "ablation"]
    reliability_rows: list[pd.DataFrame] = []
    for keys, group in calibration.groupby(group_columns, dropna=False):
        bins = calibration_reliability(group["actual"].astype(int), group["probability"].to_numpy())
        for name, value in zip(group_columns, keys, strict=True):
            bins[name] = value
        reliability_rows.append(bins)
    reliability = pd.concat(reliability_rows, ignore_index=True)
    return calibration, reliability[bin_columns]


def write_experiment_artifacts(
    experiment_dir: Path,
    manifest: dict[str, Any],
    model_results: pd.DataFrame,
    aggregate: pd.DataFrame,
    predictions: pd.DataFrame,
    final_results: pd.DataFrame,
    calibration_data: pd.DataFrame | None = None,
    reliability_bins: pd.DataFrame | None = None,
    ablation_results: pd.DataFrame | None = None,
    ablation_aggregate: pd.DataFrame | None = None,
    ablation_predictions: pd.DataFrame | None = None,
) -> None:
    """Write the immutable, auditable artifact set for one completed run."""
    write_json(experiment_dir / "manifest.json", manifest)
    write_json(experiment_dir / "config.json", manifest.get("configuration", {}))
    model_results.to_csv(experiment_dir / "model_results.csv", index=False)
    aggregate.to_csv(experiment_dir / "aggregate_results.csv", index=False)
    predictions.to_csv(experiment_dir / "out_of_fold_predictions.csv.gz", index=False, compression="gzip")
    final_results.to_csv(experiment_dir / "final_holdout_results.csv", index=False)
    calibration_columns = ["phase", "fold", "context", "task", "algorithm", "analysis_type", "ablation", "race_id", "driver_id", "actual", "probability", "threshold"]
    reliability_columns = ["phase", "fold", "context", "task", "algorithm", "analysis_type", "ablation", "bin", "bin_lower", "bin_upper", "count", "mean_predicted_probability", "observed_positive_rate"]
    calibration_data = calibration_data if calibration_data is not None else pd.DataFrame(columns=calibration_columns)
    reliability_bins = reliability_bins if reliability_bins is not None else pd.DataFrame(columns=reliability_columns)
    calibration_data.to_csv(experiment_dir / "calibration_predictions.csv.gz", index=False, compression="gzip")
    reliability_bins.to_csv(experiment_dir / "reliability_bins.csv", index=False)
    if ablation_results is not None and ablation_aggregate is not None and ablation_predictions is not None:
        ablation_dir = experiment_dir / "ablations"
        ablation_dir.mkdir(exist_ok=False)
        ablation_results.to_csv(ablation_dir / "model_results.csv", index=False)
        ablation_aggregate.to_csv(ablation_dir / "aggregate_results.csv", index=False)
        ablation_predictions.to_csv(ablation_dir / "out_of_fold_predictions.csv.gz", index=False, compression="gzip")
    write_markdown_report(experiment_dir / "report.md", manifest, aggregate, final_results)


def validate_artifact_schema(experiment_dir: Path) -> None:
    """Small fail-fast contract check useful to both tests and CI verification."""
    required = {
        "manifest.json",
        "config.json",
        "model_results.csv",
        "aggregate_results.csv",
        "out_of_fold_predictions.csv.gz",
        "calibration_predictions.csv.gz",
        "reliability_bins.csv",
        "final_holdout_results.csv",
        "report.md",
    }
    missing = sorted(name for name in required if not (experiment_dir / name).is_file())
    if missing:
        raise ValueError(f"Experiment artifacts missing required files: {', '.join(missing)}")
    manifest = json.loads((experiment_dir / "manifest.json").read_text(encoding="utf-8"))
    required_manifest = {"experiment_id", "seed", "train_seasons", "evaluation_season", "feature_columns", "data_fingerprints"}
    absent = sorted(required_manifest - set(manifest))
    if absent:
        raise ValueError(f"Manifest missing required keys: {', '.join(absent)}")
    predictions = pd.read_csv(experiment_dir / "out_of_fold_predictions.csv.gz")
    required_prediction_columns = {"race_id", "driver_id", "fold", "task", "context", "algorithm", "analysis_type", "actual", "prediction", "probability"}
    absent_prediction_columns = sorted(required_prediction_columns - set(predictions.columns))
    if absent_prediction_columns:
        raise ValueError(f"Prediction artifact missing columns: {', '.join(absent_prediction_columns)}")
    reliability = pd.read_csv(experiment_dir / "reliability_bins.csv")
    required_reliability_columns = {"task", "context", "algorithm", "analysis_type", "bin", "count", "mean_predicted_probability", "observed_positive_rate"}
    absent_reliability_columns = sorted(required_reliability_columns - set(reliability.columns))
    if absent_reliability_columns:
        raise ValueError(f"Reliability artifact missing columns: {', '.join(absent_reliability_columns)}")


def generate_thesis_figures(experiment_dir: Path) -> list[Path]:
    """Generate all figures from persisted CSV artifacts, suitable for Docker CI."""
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    aggregate = pd.read_csv(experiment_dir / "aggregate_results.csv")
    predictions = pd.read_csv(experiment_dir / "out_of_fold_predictions.csv.gz")
    reliability = pd.read_csv(experiment_dir / "reliability_bins.csv")
    ablation_aggregate = pd.read_csv(experiment_dir / "ablations" / "aggregate_results.csv")
    figure_dir = experiment_dir / "figures"
    figure_dir.mkdir(exist_ok=False)
    paths: list[Path] = []

    for task, rows in aggregate.groupby("task", sort=True):
        metric = PRIMARY_METRIC[task]
        rows = rows.sort_values("primary_score", ascending=metric in LOWER_IS_BETTER)
        labels = (rows["context"] + " / " + rows["algorithm"]).tolist()
        figure, axis = plt.subplots(figsize=(max(8, len(labels) * 0.8), 5))
        axis.bar(range(len(rows)), rows["primary_score"], color="#d71920")
        axis.set_xticks(range(len(rows)), labels, rotation=40, ha="right")
        axis.set_ylabel(metric)
        axis.set_title(f"Model leaderboard: {task}")
        figure.tight_layout()
        path = figure_dir / f"leaderboard_{task}.png"
        figure.savefig(path, dpi=160)
        plt.close(figure)
        paths.append(path)

    champions = aggregate[aggregate["champion"]].copy()
    if champions["context"].nunique() > 1:
        figure, axis = plt.subplots(figsize=(10, 5))
        tasks = sorted(champions["task"].unique())
        width = 0.35
        for offset, context in enumerate(sorted(champions["context"].unique())):
            rows = champions[champions["context"] == context].set_index("task").reindex(tasks)
            axis.bar(np.arange(len(tasks)) + (offset - 0.5) * width, rows["primary_score"], width, label=context)
        axis.set_xticks(np.arange(len(tasks)), tasks, rotation=20, ha="right")
        axis.set_ylabel("task-specific primary metric")
        axis.set_title("Pre-qualifying versus post-qualifying champion performance")
        axis.legend()
        figure.tight_layout()
        path = figure_dir / "context_performance_comparison.png"
        figure.savefig(path, dpi=160)
        plt.close(figure)
        paths.append(path)

    champion_keys = set(zip(champions["context"], champions["task"], champions["algorithm"]))
    selected_predictions = predictions[predictions.apply(lambda row: (row["context"], row["task"], row["algorithm"]) in champion_keys, axis=1)]
    for task in ["position_model", "position_gain_model"]:
        rows = selected_predictions[selected_predictions["task"] == task]
        rows = rows.assign(
            actual_numeric=pd.to_numeric(rows["actual"], errors="coerce"),
            prediction_numeric=pd.to_numeric(rows["prediction"], errors="coerce"),
        ).dropna(subset=["actual_numeric", "prediction_numeric"])
        if rows.empty:
            continue
        figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        axes[0].scatter(rows["actual_numeric"], rows["prediction_numeric"], alpha=0.45, color="#d71920")
        lower = float(min(rows["actual_numeric"].min(), rows["prediction_numeric"].min()))
        upper = float(max(rows["actual_numeric"].max(), rows["prediction_numeric"].max()))
        axes[0].plot([lower, upper], [lower, upper], "k--", linewidth=1)
        axes[0].set(xlabel="Actual", ylabel="Predicted", title=f"Predicted versus actual: {task}")
        axes[1].hist(rows["prediction_numeric"] - rows["actual_numeric"], bins=20, color="#4c78a8")
        axes[1].axvline(0, color="black", linestyle="--", linewidth=1)
        axes[1].set(xlabel="Prediction error", ylabel="Rows", title="Error distribution")
        figure.tight_layout()
        path = figure_dir / f"regression_{task}.png"
        figure.savefig(path, dpi=160)
        plt.close(figure)
        paths.append(path)

    for task in ["top10_model", "podium_model"]:
        rows = selected_predictions[selected_predictions["task"] == task]
        rows = rows.assign(
            actual_numeric=rows["actual"].astype(str).str.strip().str.lower().map({"true": 1, "false": 0, "1": 1, "0": 0}),
            probability_numeric=pd.to_numeric(rows["probability"], errors="coerce"),
        ).dropna(subset=["actual_numeric", "probability_numeric"])
        if rows.empty or rows["actual"].nunique() < 2:
            continue
        figure, axes = plt.subplots(1, 3, figsize=(14, 4.5))
        for context, group in rows.groupby("context"):
            if group["actual_numeric"].nunique() < 2:
                continue
            fpr, tpr, _ = roc_curve(group["actual_numeric"], group["probability_numeric"])
            precision, recall, _ = precision_recall_curve(group["actual_numeric"], group["probability_numeric"])
            axes[0].plot(fpr, tpr, label=context)
            axes[1].plot(recall, precision, label=context)
        axes[0].plot([0, 1], [0, 1], "k--", linewidth=1)
        axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="ROC")
        axes[1].set(xlabel="Recall", ylabel="Precision", title="Precision-recall")
        reliability_rows = reliability[(reliability["task"] == task) & (reliability["analysis_type"] == "candidate_model")]
        reliability_rows = reliability_rows[reliability_rows.apply(lambda row: (row["context"], row["task"], row["algorithm"]) in champion_keys, axis=1)]
        for context, group in reliability_rows.groupby("context"):
            group = group.groupby("bin", as_index=False).agg({"count": "sum", "mean_predicted_probability": "mean", "observed_positive_rate": "mean"})
            group = group[group["count"] > 0]
            axes[2].plot(group["mean_predicted_probability"], group["observed_positive_rate"], marker="o", label=context)
        axes[2].plot([0, 1], [0, 1], "k--", linewidth=1)
        axes[2].set(xlabel="Mean predicted probability", ylabel="Observed positive rate", title="Calibration")
        for axis in axes:
            axis.legend()
        figure.suptitle(f"Classification analysis: {task}")
        figure.tight_layout()
        path = figure_dir / f"classification_{task}.png"
        figure.savefig(path, dpi=160)
        plt.close(figure)
        paths.append(path)

    if not ablation_aggregate.empty:
        figure, axis = plt.subplots(figsize=(12, 5))
        labels = (ablation_aggregate["context"] + " / " + ablation_aggregate["task"] + " / " + ablation_aggregate["ablation"]).tolist()
        axis.bar(range(len(ablation_aggregate)), ablation_aggregate["primary_score"], color="#4c78a8")
        axis.set_xticks(range(len(ablation_aggregate)), labels, rotation=45, ha="right")
        axis.set_ylabel("task-specific primary metric")
        axis.set_title("Feature-ablation comparison (validation-selected subset champions)")
        figure.tight_layout()
        path = figure_dir / "feature_ablation_comparison.png"
        figure.savefig(path, dpi=160)
        plt.close(figure)
        paths.append(path)
    return paths


def promote_champions(
    deployment_dir: Path,
    experiment_dir: Path,
    champions: dict[tuple[str, TaskName], tuple[Any, dict[str, Any]]],
    aggregate: pd.DataFrame,
    feature_columns: dict[str, list[str]],
    manifest: dict[str, Any],
) -> None:
    """Atomically replace only production filenames after all experiment work succeeds."""
    deployment_dir.mkdir(parents=True, exist_ok=True)
    staged_dir = experiment_dir / "champions"
    staged_dir.mkdir(exist_ok=True)
    metadata_by_context: dict[str, dict[str, Any]] = {}
    importances_by_context: dict[str, dict[str, dict[str, float]]] = {}
    for (context, task), (model, final_result) in champions.items():
        staged_path = staged_dir / f"{context}_{MODEL_FILENAMES[task]}"
        joblib.dump(model, staged_path, compress=3)
        model_summary = aggregate[(aggregate["context"] == context) & (aggregate["task"] == task)].copy()
        candidate_rows = model_summary.to_dict(orient="records")
        champion_row = model_summary[model_summary["champion"]].iloc[0].to_dict()
        context_metadata = metadata_by_context.setdefault(
            context,
            {
                "trained_at": manifest["completed_at"],
                "experiment_id": manifest["experiment_id"],
                "feature_context": context,
                "train_seasons": manifest["train_seasons"],
                "test_season": manifest["evaluation_season"],  # frontend compatibility
                "evaluation_season": manifest["evaluation_season"],
                "seed": manifest["seed"],
                "data_fingerprint": manifest["data_fingerprints"][context]["sha256"],
                "feature_columns": feature_columns[context],
                "models": {},
                "candidate_summary": {},
                "champion_details": {},
            },
        )
        final_metrics = {key: value for key, value in final_result.items() if key not in {"phase", "fold", "context", "task", "algorithm", "train_rows", "validation_rows"}}
        context_metadata["models"][task] = {"algorithm": champion_row["algorithm"], **final_metrics}
        context_metadata["candidate_summary"][task] = candidate_rows
        context_metadata["champion_details"][task] = {"validation": champion_row, "final_holdout": final_metrics}
        importances_by_context.setdefault(context, {})[task] = feature_importances(model, feature_columns[context])

    # Stage metadata first.  The app sees a complete matching metadata file
    # only after each corresponding joblib has been copied into place.
    for context, context_metadata in metadata_by_context.items():
        write_json(staged_dir / f"{context}_model_metadata.json", context_metadata)
        write_json(staged_dir / f"{context}_feature_importances.json", importances_by_context[context])
    for staged_file in staged_dir.iterdir():
        if staged_file.is_file():
            shutil.copy2(staged_file, deployment_dir / staged_file.name)


def run_experiment(args: argparse.Namespace) -> Path:
    evaluation_seasons = args.evaluation_seasons or ([args.test_season] if args.test_season is not None else [])
    validate_season_arguments(args.train_seasons, evaluation_seasons, args.min_train_seasons)
    contexts = normalise_contexts(args.context)
    experiment_id = args.experiment_id or f"f1-{evaluation_seasons[0]}holdout-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    artifacts_root = resolve_path(args.artifact_output_dir)
    experiment_dir = artifacts_root / "experiments" / experiment_id
    if experiment_dir.exists():
        raise FileExistsError(f"Experiment artifact directory already exists: {experiment_dir}")
    experiment_dir.mkdir(parents=True, exist_ok=False)
    deployment_dir = resolve_path(args.deployment_output_dir)
    all_seasons = sorted([*args.train_seasons, *evaluation_seasons])
    folds = generate_temporal_folds(args.train_seasons, args.min_train_seasons)
    completeness: dict[str, list[dict[str, Any]]] = {}
    frames: dict[str, pd.DataFrame] = {}
    fingerprints: dict[str, dict[str, Any]] = {}
    for context in contexts:
        completeness[context] = validate_completed_seasons(all_seasons, context, args.as_of_date)
        frames[context] = load_feature_dataframe(context, all_seasons)
        fingerprints[context] = data_fingerprint(frames[context], CONTEXT_FEATURE_COLS[context])

    result_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    candidates_by_task: dict[tuple[str, TaskName], list[Candidate]] = {}
    for context in contexts:
        frame = frames[context]
        for task in TASK_TARGETS:
            candidates = candidate_factories(task, context, CONTEXT_FEATURE_COLS[context])
            candidates_by_task[(context, task)] = candidates
            for fold_number, fold in enumerate(folds, start=1):
                train_df = frame[frame["season_year"].isin(fold.train_seasons)].copy()
                validation_df = frame[frame["season_year"] == fold.validation_season].copy()
                for candidate_number, candidate in enumerate(candidates, start=1):
                    result, prediction_df, _ = evaluate_candidate(
                        candidate, task, context, train_df, validation_df, CONTEXT_FEATURE_COLS[context], fold.name,
                        args.seed + fold_number * 100 + candidate_number, "validation",
                    )
                    result_rows.append(result)
                    prediction_frames.append(prediction_df)

    validation_results = pd.DataFrame(result_rows)
    aggregate = aggregate_validation_results(validation_results, candidates_by_task)
    champion_models: dict[tuple[str, TaskName], tuple[Any, dict[str, Any]]] = {}
    final_rows: list[dict[str, Any]] = []
    holdout_year = evaluation_seasons[0]
    for context in contexts:
        frame = frames[context]
        development_df = frame[frame["season_year"].isin(args.train_seasons)].copy()
        holdout_df = frame[frame["season_year"] == holdout_year].copy()
        for task in TASK_TARGETS:
            selected = aggregate[(aggregate["context"] == context) & (aggregate["task"] == task) & aggregate["champion"]]
            if len(selected) != 1:
                raise RuntimeError(f"Expected exactly one validation champion for {context}/{task}.")
            selected_name = str(selected.iloc[0]["algorithm"])
            candidate = next(item for item in candidates_by_task[(context, task)] if item.name == selected_name)
            result, prediction_df, model = evaluate_candidate(
                candidate, task, context, development_df, holdout_df, CONTEXT_FEATURE_COLS[context], f"holdout_{holdout_year}",
                args.seed + 10000 + len(champion_models), "final_holdout",
            )
            result_rows.append(result)
            final_rows.append(result)
            prediction_frames.append(prediction_df)
            champion_models[(context, task)] = (model, result)

    # Each feature subset receives the same candidate matrix and temporal
    # folds.  Its own winner is validation-selected, then clearly persisted as
    # a feature-ablation analysis rather than a deployment candidate.
    ablation_rows: list[dict[str, Any]] = []
    ablation_prediction_frames: list[pd.DataFrame] = []
    for context in contexts:
        frame = frames[context]
        for task in TASK_TARGETS:
            for ablation_index, (ablation_name, ablation_features) in enumerate(feature_ablation_sets(context).items(), start=1):
                for candidate_number, ablation_candidate in enumerate(candidate_factories(task, context, ablation_features), start=1):
                    for fold_number, fold in enumerate(folds, start=1):
                        train_df = frame[frame["season_year"].isin(fold.train_seasons)].copy()
                        validation_df = frame[frame["season_year"] == fold.validation_season].copy()
                        result, prediction_df, _ = evaluate_candidate(
                            ablation_candidate,
                            task,
                            context,
                            train_df,
                            validation_df,
                            ablation_features,
                            fold.name,
                            args.seed + 20000 + ablation_index * 1000 + fold_number * 100 + candidate_number,
                            "validation",
                            analysis_type="feature_ablation",
                            ablation=ablation_name,
                        )
                        ablation_rows.append(result)
                        ablation_prediction_frames.append(prediction_df)

    all_results = pd.DataFrame(result_rows)
    oof_predictions = pd.concat(prediction_frames, ignore_index=True)
    final_results = pd.DataFrame(final_rows)
    ablation_results = pd.DataFrame(ablation_rows)
    ablation_predictions = pd.concat(ablation_prediction_frames, ignore_index=True)
    ablation_aggregate = aggregate_ablation_results(ablation_results)
    calibration_data, reliability_bins = build_calibration_artifacts(pd.concat([oof_predictions, ablation_predictions], ignore_index=True))
    completed_at = datetime.now(UTC).isoformat()
    manifest = {
        "experiment_id": experiment_id,
        "status": "completed",
        "created_at": completed_at,
        "completed_at": completed_at,
        "seed": args.seed,
        "train_seasons": sorted(args.train_seasons),
        "evaluation_season": holdout_year,
        "contexts": contexts,
        "feature_columns": {context: CONTEXT_FEATURE_COLS[context] for context in contexts},
        "weather_policy": "excluded_pending_prediction_cutoff_provenance",
        "sample_counts": {context: {str(year): int(count) for year, count in frames[context].groupby("season_year").size().items()} for context in contexts},
        "data_fingerprints": fingerprints,
        "season_completeness": completeness,
        "folds": [{"name": fold.name, "train_seasons": list(fold.train_seasons), "validation_season": fold.validation_season} for fold in folds],
        "package_versions": package_versions(),
        "python": sys.version,
        "platform": platform.platform(),
        "candidate_algorithms": {f"{context}:{task}": [candidate.name for candidate in candidates] for (context, task), candidates in candidates_by_task.items()},
        "feature_ablations": {context: feature_ablation_sets(context) for context in contexts},
        "configuration": {
            "min_train_seasons": args.min_train_seasons,
            "validation_strategy": "expanding_rolling_origin_by_completed_season",
            "selection_rule": "best_mean_primary_validation_metric_with_simpler_model_tie_break",
            "classification_threshold_rule": "F1_on_last_inner_training_season_only",
            "final_holdout_used_for_selection": False,
            "feature_ablation_method": "same_candidate_matrix_and_temporal_folds_with_validation_only_selection",
        },
    }
    write_experiment_artifacts(
        experiment_dir,
        manifest,
        all_results,
        aggregate,
        oof_predictions,
        final_results,
        calibration_data,
        reliability_bins,
        ablation_results,
        ablation_aggregate,
        ablation_predictions,
    )
    validate_artifact_schema(experiment_dir)
    if args.generate_plots:
        generated = generate_thesis_figures(experiment_dir)
        LOGGER.info("Generated %s thesis figures in %s", len(generated), experiment_dir / "figures")
    # Promotion is intentionally last: an exception during comparison or artifact
    # writing leaves the currently deployed joblibs untouched.
    promote_champions(deployment_dir, experiment_dir, champion_models, aggregate, {context: CONTEXT_FEATURE_COLS[context] for context in contexts}, manifest)
    LOGGER.info("Experiment %s completed; artifacts: %s", experiment_id, experiment_dir)
    return experiment_dir


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    np.random.seed(args.seed)
    output = run_experiment(args)
    print(f"Experiment completed: {output}")


if __name__ == "__main__":
    main()
