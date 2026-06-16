from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from lightgbm import LGBMRegressor
from sqlalchemy import text
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
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

from ingestion.db_helpers import get_sync_engine
from app.models.ml_feature import POST_QUALIFYING, PRE_QUALIFYING

LOGGER = logging.getLogger("ml.train_models")

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
CONTEXT_FEATURE_COLS = {
    PRE_QUALIFYING: PRE_QUALIFYING_FEATURE_COLS,
    POST_QUALIFYING: POST_QUALIFYING_FEATURE_COLS,
}
MODEL_NAMES = {
    "position_model": "position_model.joblib",
    "top10_model": "top10_model.joblib",
    "podium_model": "podium_model.joblib",
    "position_gain_model": "position_gain_model.joblib",
}

TARGET_POSITION = "actual_finishing_position"
TARGET_TOP10 = "finished_top10"
TARGET_PODIUM = "finished_podium"
TARGET_GAIN = "position_gain_loss"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train F1 prediction models.")
    parser.add_argument("--train-seasons", nargs="+", type=int, required=True)
    parser.add_argument("--test-season", type=int, required=True)
    parser.add_argument(
        "--context",
        "--feature-context",
        dest="context",
        choices=[PRE_QUALIFYING, POST_QUALIFYING, "all"],
        default=POST_QUALIFYING,
    )
    parser.add_argument("--model-output-dir", default="models_store/")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logs_dir / "train_models.log")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[stdout_handler, file_handler], force=True)


def resolve_output_dir(path_value: str) -> Path:
    output_dir = Path(path_value)
    if not output_dir.is_absolute():
        output_dir = PROJECT_DIR / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def load_feature_dataframe(feature_context: str) -> pd.DataFrame:
    query = """
        SELECT
            mf.race_id,
            mf.driver_id,
            mf.feature_context,
            s.year AS season_year,
            mf.grid_position,
            mf.qualifying_position,
            mf.gap_to_pole_ms,
            mf.avg_race_pace_ms,
            mf.driver_recent_form,
            mf.team_recent_form,
            mf.circuit_history_avg_finish,
            mf.circuit_history_dnf_rate,
            mf.dnf_rate_recent,
            mf.weather_is_wet,
            mf.avg_track_temp_c,
            rr.finishing_position AS actual_finishing_position,
            CASE
                WHEN rr.race_id IS NULL THEN NULL
                WHEN rr.finishing_position <= 10 THEN TRUE
                ELSE FALSE
            END AS finished_top10,
            CASE
                WHEN rr.race_id IS NULL THEN NULL
                WHEN rr.finishing_position <= 3 THEN TRUE
                ELSE FALSE
            END AS finished_podium,
            CASE
                WHEN rr.grid_position IS NULL OR rr.finishing_position IS NULL THEN NULL
                ELSE rr.grid_position - rr.finishing_position
            END AS position_gain_loss
        FROM ml_features mf
        JOIN races r ON r.id = mf.race_id
        JOIN seasons s ON s.id = r.season_id
        LEFT JOIN race_results rr
            ON rr.race_id = mf.race_id
            AND rr.driver_id = mf.driver_id
        WHERE mf.feature_context = :feature_context
    """
    df = pd.read_sql_query(text(query), get_sync_engine(), params={"feature_context": feature_context})
    if feature_context == POST_QUALIFYING:
        df = df[df["grid_position"].notna() & df["qualifying_position"].notna()].copy()
    df["weather_is_wet"] = df["weather_is_wet"].astype(float)
    return df


def validate_split(train_seasons: list[int], test_season: int) -> None:
    if any(season >= test_season for season in train_seasons):
        raise ValueError("Strict time split requires every train season to be before the test season.")


def split_train_test(
    df: pd.DataFrame,
    train_seasons: list[int],
    test_season: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_df = df[df["season_year"].isin(train_seasons)].copy()
    test_df = df[df["season_year"] == test_season].copy()
    LOGGER.info("Training samples: %s, Test samples: %s", len(train_df), len(test_df))
    if len(test_df) < 50:
        LOGGER.warning("Test set has fewer than 50 samples: %s", len(test_df))
    return train_df, test_df


def build_preprocessor(feature_cols: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[("numeric", numeric_pipeline, feature_cols)],
        remainder="drop",
    )


def build_pipeline(model: Any, feature_cols: list[str]) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor(feature_cols)),
            ("model", model),
        ]
    )


def rmse_score(y_true: pd.Series, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": rmse_score(y_true, y_pred),
        "r2": float(r2_score(y_true, y_pred)),
    }


def classification_metrics(y_true: pd.Series, y_pred: np.ndarray, y_proba: np.ndarray) -> dict[str, float]:
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))
    except ValueError:
        metrics["roc_auc"] = float("nan")
    return metrics


def fit_evaluate_regressor(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    target_col: str,
    candidates: dict[str, Any],
    feature_cols: list[str],
) -> tuple[str, Pipeline, dict[str, dict[str, float]]]:
    train_target = train_df[train_df[target_col].notna()].copy()
    test_target = test_df[test_df[target_col].notna()].copy()
    if train_target.empty or test_target.empty:
        raise ValueError(f"Not enough data to train/evaluate target {target_col}.")

    results: dict[str, dict[str, float]] = {}
    fitted_models: dict[str, Pipeline] = {}
    LOGGER.info("%-24s %-10s %-10s %-10s", "Algorithm", "MAE", "RMSE", "R2")

    for algorithm, model in candidates.items():
        pipeline = build_pipeline(model, feature_cols)
        pipeline.fit(train_target[feature_cols], train_target[target_col])
        predictions = pipeline.predict(test_target[feature_cols])
        metrics = regression_metrics(test_target[target_col], predictions)
        results[algorithm] = metrics
        fitted_models[algorithm] = pipeline
        LOGGER.info(
            "%-24s %-10.4f %-10.4f %-10.4f",
            algorithm,
            metrics["mae"],
            metrics["rmse"],
            metrics["r2"],
        )

    best_algorithm = min(results, key=lambda name: results[name]["mae"])
    return best_algorithm, fitted_models[best_algorithm], results


def scale_pos_weight(y_train: pd.Series) -> float:
    positives = int((y_train == 1).sum())
    negatives = int((y_train == 0).sum())
    if positives == 0:
        return 1.0
    return negatives / positives


def fit_evaluate_classifier(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str],
) -> tuple[Pipeline, dict[str, float]]:
    train_target = train_df[train_df[target_col].notna()].copy()
    test_target = test_df[test_df[target_col].notna()].copy()
    if train_target.empty or test_target.empty:
        raise ValueError(f"Not enough data to train/evaluate target {target_col}.")

    y_train = train_target[target_col].astype(int)
    y_test = test_target[target_col].astype(int)
    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight(y_train),
        random_state=42,
        eval_metric="logloss",
    )
    pipeline = build_pipeline(model, feature_cols)
    pipeline.fit(train_target[feature_cols], y_train)
    predictions = pipeline.predict(test_target[feature_cols])
    probabilities = pipeline.predict_proba(test_target[feature_cols])[:, 1]
    return pipeline, classification_metrics(y_test, predictions, probabilities)


def train_position_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: Path,
    feature_context: str,
    feature_cols: list[str],
) -> tuple[Pipeline, dict[str, Any]]:
    candidates = {
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            random_state=42,
        ),
        "XGBRegressor": XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            random_state=42,
        ),
        "LGBMRegressor": LGBMRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            random_state=42,
            verbose=-1,
        ),
    }
    best_algorithm, best_model, all_results = fit_evaluate_regressor(
        train_df,
        test_df,
        TARGET_POSITION,
        candidates,
        feature_cols,
    )
    joblib.dump(best_model, output_dir / f"{feature_context}_{MODEL_NAMES['position_model']}", compress=3)
    return best_model, {"algorithm": best_algorithm, **all_results[best_algorithm]}


def train_top10_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: Path,
    feature_context: str,
    feature_cols: list[str],
) -> tuple[Pipeline, dict[str, Any]]:
    model, metrics = fit_evaluate_classifier(train_df, test_df, TARGET_TOP10, feature_cols)
    joblib.dump(model, output_dir / f"{feature_context}_{MODEL_NAMES['top10_model']}", compress=3)
    return model, {"algorithm": "XGBClassifier", **metrics}


def train_podium_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: Path,
    feature_context: str,
    feature_cols: list[str],
) -> tuple[Pipeline, dict[str, Any]]:
    model, metrics = fit_evaluate_classifier(train_df, test_df, TARGET_PODIUM, feature_cols)
    joblib.dump(model, output_dir / f"{feature_context}_{MODEL_NAMES['podium_model']}", compress=3)
    return model, {"algorithm": "XGBClassifier", **metrics}


def train_position_gain_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: Path,
    feature_context: str,
    feature_cols: list[str],
) -> tuple[Pipeline, dict[str, Any]]:
    candidates = {
        "LGBMRegressor": LGBMRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            random_state=42,
            verbose=-1,
        )
    }
    best_algorithm, model, results = fit_evaluate_regressor(train_df, test_df, TARGET_GAIN, candidates, feature_cols)
    joblib.dump(model, output_dir / f"{feature_context}_{MODEL_NAMES['position_gain_model']}", compress=3)
    return model, {"algorithm": best_algorithm, **results[best_algorithm]}


def feature_importances(model: Pipeline, feature_cols: list[str]) -> dict[str, float]:
    estimator = model.named_steps["model"]
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        return {}
    return {
        feature_name: float(importance)
        for feature_name, importance in zip(feature_cols, importances, strict=False)
    }


def top_features(importances: dict[str, float], count: int = 5) -> list[tuple[str, float]]:
    return sorted(importances.items(), key=lambda item: item[1], reverse=True)[:count]


def format_metrics(metrics: dict[str, Any]) -> str:
    return ", ".join(
        f"{key}={value:.4f}" if isinstance(value, float) and np.isfinite(value) else f"{key}={value}"
        for key, value in metrics.items()
        if key != "algorithm"
    )


def build_report(
    metadata: dict[str, Any],
    feature_importance_data: dict[str, dict[str, float]],
) -> str:
    lines = [
        "F1 Model Evaluation Report",
        f"Trained at: {metadata['trained_at']}",
        f"Feature context: {metadata['feature_context']}",
        f"Train seasons: {metadata['train_seasons']}",
        f"Test season: {metadata['test_season']}",
        "",
    ]
    for model_name, metrics in metadata["models"].items():
        lines.append(f"{model_name}")
        lines.append(f"  Algorithm: {metrics['algorithm']}")
        lines.append(f"  Metrics: {format_metrics(metrics)}")
        lines.append("  Top features:")
        for feature_name, importance in top_features(feature_importance_data.get(model_name, {})):
            lines.append(f"    {feature_name}: {importance:.6f}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(json_safe(data), output_file, indent=2, sort_keys=True, allow_nan=False)


def train_context(
    feature_context: str,
    train_seasons: list[int],
    test_season: int,
    output_dir: Path,
) -> str:
    feature_cols = CONTEXT_FEATURE_COLS[feature_context]
    LOGGER.info("Training %s model family with features=%s", feature_context, feature_cols)

    df = load_feature_dataframe(feature_context)
    train_df, test_df = split_train_test(df, train_seasons, test_season)
    if train_df.empty:
        raise RuntimeError(f"{feature_context} training set is empty.")
    if test_df.empty:
        raise RuntimeError(f"{feature_context} test set is empty.")

    trained_models: dict[str, Pipeline] = {}
    model_metadata: dict[str, dict[str, Any]] = {}

    LOGGER.info("[%s] Training finishing position regression candidates", feature_context)
    trained_models["position_model"], model_metadata["position_model"] = train_position_model(
        train_df,
        test_df,
        output_dir,
        feature_context,
        feature_cols,
    )

    LOGGER.info("[%s] Training top10 classifier", feature_context)
    trained_models["top10_model"], model_metadata["top10_model"] = train_top10_model(
        train_df,
        test_df,
        output_dir,
        feature_context,
        feature_cols,
    )

    LOGGER.info("[%s] Training podium classifier", feature_context)
    trained_models["podium_model"], model_metadata["podium_model"] = train_podium_model(
        train_df,
        test_df,
        output_dir,
        feature_context,
        feature_cols,
    )

    LOGGER.info("[%s] Training position gain/loss regressor", feature_context)
    trained_models["position_gain_model"], model_metadata["position_gain_model"] = train_position_gain_model(
        train_df,
        test_df,
        output_dir,
        feature_context,
        feature_cols,
    )

    feature_importance_data = {
        model_name: feature_importances(model, feature_cols)
        for model_name, model in trained_models.items()
    }

    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "feature_context": feature_context,
        "train_seasons": train_seasons,
        "test_season": test_season,
        "models": model_metadata,
        "feature_columns": feature_cols,
        "feature_importances": feature_importance_data,
    }

    write_json(output_dir / f"{feature_context}_feature_importances.json", feature_importance_data)
    write_json(output_dir / f"{feature_context}_model_metadata.json", metadata)

    report = build_report(metadata, feature_importance_data)
    (output_dir / f"{feature_context}_evaluation_report.txt").write_text(report, encoding="utf-8")
    LOGGER.info("[%s] Training complete", feature_context)
    return report


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    validate_split(args.train_seasons, args.test_season)
    output_dir = resolve_output_dir(args.model_output_dir)

    contexts = [PRE_QUALIFYING, POST_QUALIFYING] if args.context == "all" else [args.context]
    reports = [
        train_context(context, args.train_seasons, args.test_season, output_dir)
        for context in contexts
    ]
    report = "\n\n".join(reports)
    print(report)


if __name__ == "__main__":
    main()
