"""Predeclared hyperparameter search spaces and inner chronological selection."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor

from ml_pipeline.preprocessing import build_pipeline
from ml_pipeline.temporal_splits import generate_temporal_folds

REGRESSION_SEARCH_SPACES: dict[str, list[dict[str, Any]]] = {
    "Ridge": [{"alpha": a} for a in (0.1, 1.0, 10.0, 100.0)],
    "ElasticNet": [
        {"alpha": a, "l1_ratio": r}
        for a in (0.01, 0.05, 0.1, 1.0)
        for r in (0.1, 0.5, 0.9)
    ],
    "RandomForestRegressor": [
        {"n_estimators": 300, "max_depth": d, "min_samples_leaf": s}
        for d in (None, 4, 8)
        for s in (1, 4)
    ],
    "XGBRegressor": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 5, 7)
        for lr in (0.02, 0.04, 0.08)
    ],
    "LGBMRegressor": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 6, -1)
        for lr in (0.02, 0.04, 0.08)
    ],
}

CLASSIFICATION_SEARCH_SPACES: dict[str, list[dict[str, Any]]] = {
    "LogisticRegression": [{"C": c} for c in (0.1, 1.0, 10.0)],
    "RandomForestClassifier": [
        {"n_estimators": 300, "max_depth": d, "min_samples_leaf": s}
        for d in (None, 4, 8)
        for s in (1, 4)
    ],
    "XGBClassifier": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 5, 7)
        for lr in (0.02, 0.04, 0.08)
    ],
    "LGBMClassifier": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 6, -1)
        for lr in (0.02, 0.04, 0.08)
    ],
}

_CLASSIFICATION = {"top10_model", "podium_model"}


def _class_weight_scale(y: pd.Series) -> float:
    positives = int((y.astype(int) == 1).sum())
    negatives = int((y.astype(int) == 0).sum())
    return float(negatives / positives) if positives else 1.0


def build_model_from_config(
    algorithm: str,
    config: dict[str, Any],
    seed: int,
    feature_cols: list[str],
    task: str,
    y: pd.Series,
) -> Any:
    """Construct an (unfitted) sklearn-compatible model for a specific config."""
    if algorithm == "Ridge":
        return Ridge(alpha=config["alpha"], random_state=seed)
    if algorithm == "ElasticNet":
        return ElasticNet(alpha=config["alpha"], l1_ratio=config["l1_ratio"], max_iter=10000, random_state=seed)
    if algorithm == "RandomForestRegressor":
        return RandomForestRegressor(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                                    min_samples_leaf=config["min_samples_leaf"], random_state=seed, n_jobs=1)
    if algorithm == "RandomForestClassifier":
        return RandomForestClassifier(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                                      min_samples_leaf=config["min_samples_leaf"], class_weight="balanced",
                                      random_state=seed, n_jobs=1)
    if algorithm == "XGBRegressor":
        return XGBRegressor(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                            learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                            reg_lambda=1.0, random_state=seed, n_jobs=1)
    if algorithm == "XGBClassifier":
        return XGBClassifier(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                             learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                             reg_lambda=1.0, scale_pos_weight=_class_weight_scale(y),
                             random_state=seed, n_jobs=1, eval_metric="logloss")
    if algorithm == "LGBMRegressor":
        return LGBMRegressor(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                             learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                             reg_lambda=1.0, random_state=seed, n_jobs=1, verbose=-1)
    if algorithm == "LGBMClassifier":
        return LGBMClassifier(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                              learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                              reg_lambda=1.0, class_weight="balanced", random_state=seed, n_jobs=1, verbose=-1)
    if algorithm == "LogisticRegression":
        return LogisticRegression(C=config["C"], max_iter=3000, class_weight="balanced", random_state=seed)
    raise ValueError(f"Unknown search algorithm: {algorithm}")


def select_hyperparameters(
    algorithm: str,
    space: list[dict[str, Any]],
    train_df: pd.DataFrame,
    target: str,
    feature_cols: list[str],
    task: str,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Select best config on an expanding inner split of train_df's seasons only."""
    is_classification = task in _CLASSIFICATION
    seasons = sorted(train_df["season_year"].unique().tolist())
    inner_folds = generate_temporal_folds(seasons, min_train_seasons=1)
    if not inner_folds:
        return space[0], [{"config": space[0], "inner_score_mean": None, "inner_scores": []}]

    records: list[dict[str, Any]] = []
    for config in space:
        scores: list[float] = []
        for fold in inner_folds:
            it = train_df[train_df["season_year"].isin(fold.train_seasons) & train_df[target].notna()]
            iv = train_df[(train_df["season_year"] == fold.validation_season) & train_df[target].notna()]
            if it.empty or iv.empty or (is_classification and (it[target].nunique() < 2 or iv[target].nunique() < 2)):
                continue
            model = build_pipeline(build_model_from_config(algorithm, config, seed, feature_cols, task, it[target]), feature_cols)
            model.fit(it[feature_cols], it[target].astype(int) if is_classification else it[target].astype(float))
            if is_classification:
                proba = model.predict_proba(iv[feature_cols])[:, 1]
                if task == "podium_model":
                    score = average_precision_score(iv[target].astype(int), proba)
                else:
                    score = roc_auc_score(iv[target].astype(int), proba) if iv[target].nunique() == 2 else 0.5
            else:
                score = mean_absolute_error(iv[target].astype(float), model.predict(iv[feature_cols]))
            scores.append(float(score))
        records.append({"config": config, "inner_score_mean": float(np.mean(scores)) if scores else None,
                        "inner_scores": scores})

    valid = [r for r in records if r["inner_score_mean"] is not None]
    if not valid:
        return space[0], records
    lower_is_better = not is_classification
    best = min(valid, key=lambda r: r["inner_score_mean"]) if lower_is_better else max(
        valid, key=lambda r: r["inner_score_mean"]
    )
    return best["config"], records
