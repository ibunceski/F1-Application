"""Leakage-safe statistical evaluation for race-clustered predictions.

The race is the sampling unit because driver-rows within one race are correlated.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    roc_auc_score,
)


def per_race_metric(preds: pd.DataFrame, metric_fn: Callable) -> pd.Series:
    values: dict[int, float] = {}
    for race_id, group in preds.groupby("race_id", sort=False):
        values[int(race_id)] = float(metric_fn(
            group["actual"].to_numpy(dtype=float),
            group["prediction"].to_numpy(dtype=float),
        ))
    return pd.Series(values, name="metric")


def bootstrap_mean_of_per_race(per_race: pd.Series, n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    values = per_race.to_numpy(dtype=float)
    means = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, len(values), size=len(values))
        means[b] = values[idx].mean()
    return {
        "mean": float(means.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
    }


def cluster_bootstrap_pooled(preds: pd.DataFrame, metric_fn: Callable, n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    races = sorted(preds["race_id"].unique())
    by_race = {int(r): preds[preds["race_id"] == r] for r in races}
    stats = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, len(races), size=len(races))
        sample = pd.concat([by_race[int(races[i])] for i in idx], ignore_index=True)
        stats[b] = float(metric_fn(sample))
    return {
        "mean": float(stats.mean()),
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
    }


def pooled_mae(preds: pd.DataFrame) -> float:
    return float(mean_absolute_error(preds["actual"], preds["prediction"]))


def pooled_roc_auc(preds: pd.DataFrame) -> float:
    y = preds["actual"].astype(int).to_numpy()
    p = preds["probability"].to_numpy(dtype=float)
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan")


def pooled_pr_auc(preds: pd.DataFrame) -> float:
    y = preds["actual"].astype(int).to_numpy()
    p = preds["probability"].to_numpy(dtype=float)
    return float(average_precision_score(y, p)) if len(np.unique(y)) == 2 else float("nan")


def pooled_brier(preds: pd.DataFrame) -> float:
    return float(brier_score_loss(preds["actual"].astype(int), preds["probability"]))


def per_race_mae(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(mean_absolute_error(actual, pred))


def per_race_brier(actual: np.ndarray, proba: np.ndarray) -> float:
    return float(brier_score_loss(actual.astype(int), np.clip(proba, 0.0, 1.0)))


def paired_metric_differences(per_race_a: pd.Series, per_race_b: pd.Series) -> pd.Series:
    frame = pd.concat([per_race_a.rename("a"), per_race_b.rename("b")], axis=1).dropna()
    return (frame["a"] - frame["b"]).rename("difference")


def paired_permutation_test(differences: pd.Series, n_perm: int = 5000, seed: int = 42) -> float:
    values = differences.to_numpy(dtype=float)
    if values.size < 2:
        return 1.0
    observed = abs(values.mean())
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perm):
        signs = rng.choice(np.array([-1.0, 1.0]), size=values.size)
        if abs((signs * values).mean()) >= observed:
            count += 1
    return float((count + 1) / (n_perm + 1))


def paired_bootstrap_ci(differences: pd.Series, n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    values = differences.to_numpy(dtype=float)
    means = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, len(values), size=len(values))
        means[b] = values[idx].mean()
    return {
        "mean": float(means.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
    }
